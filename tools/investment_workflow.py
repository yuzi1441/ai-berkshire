#!/usr/bin/env python3
"""One safe entry point for report, Checklist, and formal Drift handoffs.

Report and Checklist files must already be routed and saved under ``reports/``.
The default is a structural dry-run. ``--write`` for the ``report`` workflow
promotes the validated report to the ticker's canonical current main report,
rebuilds derived dashboard state, and validates it as one transaction: if any
step fails, the previous canonical report and the derived outputs are restored.
Checklist handoffs remain a PRE_BUY gate and never change the canonical main
report. Formal Drift delegates to the established ``thesis_drift_handoff.py``
contract. No workflow commits, pushes, deploys, or makes an investment
decision.
"""

from __future__ import annotations

import argparse
import copy
import contextlib
import fcntl
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_investment_dashboard as dashboard  # noqa: E402
import current_reports  # noqa: E402
from source_hash import canonical_file_sha256  # noqa: E402

OUTPUT_SCOPES = ("reports/00-index", "data/investment-dashboard", "site/data")
OUTPUT_EXCLUDED_PREFIXES = (
    "data/investment-dashboard/report_judgments/",
    "data/investment-dashboard/main-report-review-rules/",
    "data/investment-dashboard/quotes/",
)
PROTECTED_AUTHORITY_PATHS = {
    f"data/investment-dashboard/{name}"
    for name in (
        "post_buy_tracking.json",
        "original_buy_theses.json",
        "holding_research_reviews.json",
        "financial_facts.json",
        "decision_rules.json",
        "drift_states.json",
        "rule_lifecycle.json",
        "rule_change_log.json",
    )
}
STAGING_COPY_SCOPES = ("reports", "data", "site", "tools")


def _resolve_report(root: Path, raw: str) -> Path:
    path = Path(raw)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    reports = (root / "reports").resolve()
    if not path.is_file():
        raise ValueError(f"report does not exist: {path}")
    if not path.is_relative_to(reports) or path.parent == reports:
        raise ValueError("report must be routed below reports/<company-or-topic>/")
    if path.suffix.lower() != ".md":
        raise ValueError("report workflow accepts Markdown reports only")
    return path


def _registry(root: Path) -> list[dict[str, Any]]:
    return dashboard.load_registry(root / "data" / "report-routing" / "company_registry.json")


def _overrides(root: Path) -> dict[str, Any]:
    return dashboard.load_json(
        root / "data" / "investment-dashboard" / "overrides.json",
        {"schema_version": 1, "reports": {}, "companies": {}},
    )


def inspect_report(root: Path, path: Path, kind: str) -> dict[str, Any]:
    registry = _registry(root)
    if kind == "checklist":
        record = dashboard.checklist_record(path, root, registry)
        if record is None:
            raise ValueError("file is not a recognizable standalone investment Checklist")
    else:
        record = dashboard.candidate_record(path, root, registry, _overrides(root))
        if record is None or not dashboard.is_company_equity(record):
            raise ValueError("file is not a recognizable individual-company main report")
        if dashboard.is_post_buy_tracking_report(record):
            raise ValueError("post-buy tracking reports must use thesis-tracker, not report handoff")
        if dashboard.is_role_subreport_path(record.get("report_path")):
            raise ValueError("role/topic sub-reports cannot be promoted to the current main report")
    if not record.get("ticker"):
        raise ValueError("report ticker could not be resolved")
    if not record.get("data_cutoff"):
        raise ValueError("report has no reliable data cutoff")
    return record


def _output_files(root: Path):
    for scope in OUTPUT_SCOPES:
        base = root / scope
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if any(relative.startswith(prefix) for prefix in OUTPUT_EXCLUDED_PREFIXES):
                continue
            yield relative, path


@contextlib.contextmanager
def promotion_lock(root: Path):
    """Serialize the complete promotion transaction on macOS and Linux."""
    completed = subprocess.run(
        ["git", "rev-parse", "--git-path", "ai-berkshire-promotion.lock"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    lock_path = Path(completed.stdout.strip())
    if not lock_path.is_absolute():
        lock_path = root / lock_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _copy_staging_tree(root: Path, staging: Path) -> None:
    for scope in STAGING_COPY_SCOPES:
        source = root / scope
        if source.exists():
            shutil.copytree(source, staging / scope, symlinks=True)


def _file_map(root: Path) -> dict[str, Path]:
    return {relative: path for relative, path in _output_files(root)}


def _activate_staging(
    root: Path,
    staging: Path,
    *,
    expected_registry_sha: str,
    after_activate: Callable[[list[str]], None] | None = None,
) -> list[str]:
    """Activate validated files with a canonical CAS and per-file atomic writes.

    Build and validation happen entirely in staging. Activation is serialized
    and each file replacement is atomic, but POSIX does not provide one atomic
    rename across these three legacy output directories. The web application's
    consolidated dashboard_core.json remains an atomic generation snapshot.
    """
    canonical_relative = f"data/investment-dashboard/{current_reports.FILENAME}"
    canonical_path = root / canonical_relative
    if current_reports.file_sha256(canonical_path) != expected_registry_sha:
        raise ValueError("CANONICAL_CHANGED_DURING_PROMOTION")

    source_files = _file_map(root)
    staged_files = _file_map(staging)
    changed: list[str] = []
    for relative in sorted(set(source_files) | set(staged_files)):
        source = source_files.get(relative)
        candidate = staged_files.get(relative)
        if source is None or candidate is None or source.read_bytes() != candidate.read_bytes():
            changed.append(relative)
    protected_changes = sorted(
        relative for relative in changed if relative in PROTECTED_AUTHORITY_PATHS
    )
    if protected_changes:
        raise ValueError(
            "STAGING_CHANGED_PROTECTED_AUTHORITY: " + ", ".join(protected_changes)
        )

    # Publish derived projections first and the canonical pointer last. Every
    # individual replacement is atomic; dashboard_core.json is the browser's
    # all-in-one generation boundary.
    ordered = [relative for relative in changed if relative != canonical_relative]
    ordered.append(canonical_relative)
    originals = {
        relative: (root / relative).read_bytes() if (root / relative).is_file() else None
        for relative in ordered
    }
    try:
        for relative in ordered:
            candidate = staged_files.get(relative)
            target = root / relative
            if candidate is None:
                target.unlink(missing_ok=True)
            else:
                current_reports.write_bytes_atomic(target, candidate.read_bytes())
        if after_activate is not None:
            after_activate(changed)
    except BaseException:
        for relative, original in originals.items():
            target = root / relative
            if original is None:
                target.unlink(missing_ok=True)
            else:
                current_reports.write_bytes_atomic(target, original)
        raise
    return changed


def _build_staged_generation(
    root: Path,
    payload: dict[str, Any],
) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, Any]]:
    temporary = tempfile.TemporaryDirectory(prefix="ai-berkshire-promotion-")
    staging = Path(temporary.name) / "repo"
    staging.mkdir()
    try:
        _copy_staging_tree(root, staging)
        canonical_path = staging / "data" / "investment-dashboard" / current_reports.FILENAME
        current_reports.write_atomic(canonical_path, payload)
        manifest = Path(temporary.name) / "tracked-assets.json"
        current_reports.write_tracked_manifest(root, manifest)
        built = dashboard.build_dashboard(
            staging,
            require_canonical_reports=True,
            tracked_assets_manifest=manifest,
        )
        _validate_state(
            staging,
            require_tracked_assets=True,
            tracked_root=root,
        )
        return temporary, staging, built
    except BaseException:
        temporary.cleanup()
        raise


def _public_canonical_update(plan: dict[str, Any], *, write: bool) -> dict[str, Any]:
    status_map = {
        "promote": "promoted" if write else "would_promote",
        "same_cutoff_replacement": "same_cutoff_replacement" if write else "would_replace_same_cutoff",
        "already_current": "already_current",
    }
    return {
        "ticker": plan["ticker"],
        "company": plan.get("company"),
        "previous_report": plan.get("previous_report"),
        "new_report": plan.get("new_report"),
        "previous_cutoff": plan.get("previous_cutoff"),
        "new_cutoff": plan.get("new_cutoff"),
        "status": status_map[plan["action"]],
        "would_promote": plan["action"] != "already_current",
        "canonical_validation": "passed",
    }


def _declared_title_ticker(path: Path) -> str | None:
    """Return the ticker the report title itself declares, ignoring path/registry."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    title = dashboard.extract_title(lines, path.stem)
    declared = dashboard.extract_ticker(title or "")
    if declared:
        return declared.upper()
    paren = dashboard.US_PAREN_TICKER_PATTERN.search(title or "")
    if paren:
        token = dashboard.us_ticker_token(paren.group(1))
        if token:
            return token
    return None


def plan_canonical_promotion(
    root: Path,
    path: Path,
    record: dict[str, Any],
    *,
    require_candidate_tracked: bool = False,
) -> dict[str, Any]:
    """Plan a canonical promotion without writing anything.

    Fails closed on unregistered tickers, older data cutoffs, and reports that
    do not pass the canonical validator. The returned ``new_payload`` is only
    written by the caller inside the promotion transaction.
    """
    canonical_path = root / "data" / "investment-dashboard" / current_reports.FILENAME
    payload = current_reports.load(canonical_path, strict=True)
    assert payload is not None
    ticker = str(record.get("ticker") or "").upper()
    entries = payload.get("companies") or {}
    if ticker not in entries:
        raise ValueError(
            "NEW_TICKER_REQUIRES_BOOTSTRAP: "
            f"{ticker} is not registered in {current_reports.FILENAME}; "
            "run the canonical migration/bootstrap workflow first"
        )
    entry = entries[ticker]
    declared = _declared_title_ticker(path)
    if declared and declared != ticker:
        raise ValueError(
            f"TICKER_MISMATCH: report title declares {declared} but the canonical ticker is {ticker}"
        )
    previous_relative = str(entry.get("current_main_report") or "")
    new_relative = path.relative_to(root).as_posix()
    previous_path = root / previous_relative
    previous_sha = canonical_file_sha256(previous_path) if previous_path.is_file() else None
    new_sha = canonical_file_sha256(path)
    approved_sha = str(entry.get("content_sha256") or "").lower()
    staged_rename = bool(
        previous_relative
        and not previous_path.exists()
        and new_relative != previous_relative
        and new_sha == approved_sha
    )
    if previous_relative and previous_sha != approved_sha and not staged_rename:
        raise ValueError(
            "CANONICAL_CONTENT_CHANGED_IN_PLACE: "
            f"{previous_relative} expected {approved_sha or 'missing SHA'} got {previous_sha}"
        )
    previous_cutoff = None
    if previous_path.is_file():
        previous_record = dashboard.candidate_record(previous_path, root, _registry(root), _overrides(root))
        if previous_record:
            previous_cutoff = previous_record.get("data_cutoff")
    elif staged_rename:
        previous_sha = approved_sha
        previous_cutoff = record.get("data_cutoff")
    plan: dict[str, Any] = {
        "ticker": ticker,
        "company": entry.get("company") or record.get("company"),
        "previous_report": previous_relative or None,
        "new_report": new_relative,
        "previous_cutoff": previous_cutoff,
        "new_cutoff": record.get("data_cutoff"),
        "previous_sha256": previous_sha,
        "new_sha256": new_sha,
    }
    if new_relative == previous_relative:
        plan["action"] = "already_current"
        plan["new_payload"] = payload
        return plan
    if previous_sha and new_sha == previous_sha and not staged_rename:
        plan["action"] = "already_current"
        plan["new_payload"] = payload
        return plan
    if previous_cutoff and plan["new_cutoff"] and plan["new_cutoff"] < previous_cutoff:
        raise ValueError(
            "NEW_REPORT_OLDER_THAN_CURRENT_CANONICAL: "
            f"{ticker} new cutoff {plan['new_cutoff']} < current cutoff {previous_cutoff} "
            f"({previous_relative})"
        )
    candidate_payload: dict[str, Any] = {
        "schema_version": payload.get("schema_version", current_reports.SCHEMA_VERSION),
        "companies": {
            ticker: {
                "company": plan["company"],
                "current_main_report": new_relative,
                "content_sha256": new_sha,
            }
        },
    }
    if "legacy_tickers" in payload:
        candidate_payload["legacy_tickers"] = payload["legacy_tickers"]
    errors = current_reports.validate(
        candidate_payload,
        repo_root=root,
        registry=_registry(root),
        records_by_path={new_relative: record},
        tracked=current_reports.tracked_paths(root),
        require_tracked=require_candidate_tracked,
    )
    if errors:
        raise ValueError("canonical validation failed: " + "; ".join(errors))
    new_payload = copy.deepcopy(payload)
    new_payload.setdefault("companies", {})[ticker] = {
        "company": plan["company"],
        "current_main_report": new_relative,
        "content_sha256": new_sha,
    }
    plan["action"] = (
        "same_cutoff_replacement"
        if previous_cutoff and plan["new_cutoff"] == previous_cutoff
        else "promote"
    )
    plan["new_payload"] = new_payload
    return plan


def _validate_state(
    root: Path,
    *,
    require_tracked_assets: bool = False,
    tracked_root: Path | None = None,
) -> None:
    command = [
        sys.executable,
        str(root / "tools" / "validate_decision_state.py"),
        "--repo-root",
        str(root),
    ]
    if require_tracked_assets:
        command.append("--require-tracked-assets")
    if tracked_root is not None:
        command.extend(["--tracked-root", str(tracked_root)])
    completed = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise ValueError(
            "dashboard state validation failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )


def run_document(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repo_root.resolve()
    path = _resolve_report(root, args.path)
    record = inspect_report(root, path, args.command)
    relative = path.relative_to(root).as_posix()
    result: dict[str, Any] = {
        "status": "dry_run" if not args.write else "written",
        "workflow": args.command,
        "report_path": relative,
        "ticker": record.get("ticker"),
        "company": record.get("company"),
        "data_cutoff": record.get("data_cutoff"),
        "completed": ["structural_validation", "ticker_link_validation", "data_cutoff_validation"],
        "not_completed": ["commit", "push", "merge", "deploy", "investment_decision"],
        "dashboard_effect": "No files changed; rerun with --write to rebuild derived projections.",
        "next_skill": "none",
    }
    plan = None
    if args.command == "report":
        tracked = current_reports.tracked_paths(root)
        candidate_not_tracked = relative not in tracked
        plan = plan_canonical_promotion(root, path, record)
        result["canonical_update"] = _public_canonical_update(plan, write=False)
        result["candidate_not_tracked"] = candidate_not_tracked
        result["completed"].append("canonical_validation")
        result["dashboard_effect"] = (
            "Dry run only; no canonical or dashboard files changed. "
            f"Canonical action: {plan['action']}."
        )
    if not args.write:
        return result

    if args.command == "report":
        canonical_path = root / "data" / "investment-dashboard" / current_reports.FILENAME
        if result.get("candidate_not_tracked"):
            raise ValueError(
                "REPORT_MUST_BE_STAGED_BEFORE_PROMOTION: "
                f"git add -- {relative}"
            )
        canonical_relative = canonical_path.relative_to(root).as_posix()
        if canonical_relative not in current_reports.tracked_paths(root):
            raise ValueError(
                "CURRENT_REPORTS_MUST_BE_STAGED_BEFORE_PROMOTION: "
                f"git add -- {canonical_relative}"
            )
        with promotion_lock(root):
            # Re-plan after acquiring the lock. This is the first half of the
            # CAS contract and prevents a stale preview from being committed.
            plan = plan_canonical_promotion(
                root, path, record, require_candidate_tracked=True
            )
            expected_registry_sha = current_reports.file_sha256(canonical_path)
            temporary, staging, built = _build_staged_generation(root, plan["new_payload"])
            try:
                manifest = root / current_reports.TRACKED_MANIFEST_FILENAME
                manifest_before = manifest.read_bytes() if manifest.is_file() else None

                def refresh_manifest(changed: list[str]) -> None:
                    changed_set = set(changed)
                    try:
                        current_reports.write_bootstrap_manifest(
                            root,
                            manifest,
                            worktree_overrides=changed_set,
                        )
                        current_reports.verify_bootstrap_manifest(
                            root,
                            manifest,
                            worktree_overrides=changed_set,
                        )
                    except BaseException:
                        if manifest_before is None:
                            manifest.unlink(missing_ok=True)
                        else:
                            current_reports.write_bytes_atomic(manifest, manifest_before)
                        raise

                _activate_staging(
                    root,
                    staging,
                    expected_registry_sha=expected_registry_sha,
                    after_activate=refresh_manifest,
                )
            finally:
                temporary.cleanup()
        result["canonical_update"] = _public_canonical_update(plan, write=True)
        result["completed"].extend(
            [
                "canonical_promotion",
                "dashboard_build",
                "decision_state_validation",
                "tracked_manifest_refresh",
            ]
        )
        result["dashboard_effect"] = (
            f"Rebuilt {built.get('decision_count')} company decisions; "
            f"{plan['action']} for {plan['ticker']}."
        )
        result["next_skill"] = (
            "Review Dashboard action guidance; run a specialist Skill only if it becomes actionable."
        )
        return result

    built = dashboard.build_dashboard(root)
    _validate_state(root)
    result["completed"].extend(["dashboard_build", "decision_state_validation"])
    result["dashboard_effect"] = (
        f"Rebuilt {built.get('decision_count')} company decisions; derived state reflects {relative}."
    )
    result["next_skill"] = (
        "Review Checklist result and current action guidance; purchase remains a human decision."
    )
    return result


def run_drift(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repo_root.resolve()
    command = [
        sys.executable,
        str(root / "tools" / "thesis_drift_handoff.py"),
        args.ticker.upper(),
        "--mode", args.mode,
        "--direction", args.direction,
        "--severity", args.severity,
        "--summary", args.summary,
        "--facts-source", *args.facts_source,
        "--repo-root", str(root),
        "--write" if args.write else "--dry-run",
    ]
    if args.next_review:
        command[command.index("--facts-source"):command.index("--repo-root")] = [
            "--next-review", args.next_review,
            "--facts-source", *args.facts_source,
        ]
    completed = subprocess.run(
        command, cwd=root, check=False, capture_output=True, text=True
    )
    if completed.returncode:
        raise ValueError(completed.stderr.strip() or completed.stdout.strip())
    handoff = json.loads(completed.stdout)
    if args.write:
        _validate_state(root)
    return {
        "status": "written" if args.write else "dry_run",
        "workflow": "drift",
        "ticker": args.ticker.upper(),
        "completed": ["formal_drift_handoff_validation"] + (
            ["formal_drift_authority_write", "dashboard_build", "decision_state_validation"]
            if args.write else []
        ),
        "not_completed": ["commit", "push", "merge", "deploy", "buy_sell_decision"],
        "dashboard_effect": (
            "Formal Drift result was handed off and derived state rebuilt."
            if args.write else "No files changed; handoff contract validated only."
        ),
        "next_skill": "none; review the resulting action guidance",
        "handoff": handoff,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("report", "checklist"):
        child = subparsers.add_parser(name)
        child.add_argument("path")
        child.add_argument("--repo-root", type=Path, default=ROOT)
        child.add_argument("--write", action="store_true")
        child.set_defaults(handler=run_document)
    drift = subparsers.add_parser("drift")
    drift.add_argument("ticker")
    drift.add_argument("--mode", choices=("watch", "holding"), required=True)
    drift.add_argument("--direction", choices=("improved", "unchanged", "weakened", "unknown"), required=True)
    drift.add_argument("--severity", choices=("none", "minor", "major", "unknown"), default="none")
    drift.add_argument("--summary", required=True)
    drift.add_argument("--next-review")
    drift.add_argument("--facts-source", nargs="+", required=True)
    drift.add_argument("--repo-root", type=Path, default=ROOT)
    drift.add_argument("--write", action="store_true")
    drift.set_defaults(handler=run_drift)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
