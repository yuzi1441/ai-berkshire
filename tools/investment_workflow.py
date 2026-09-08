#!/usr/bin/env python3
"""One safe entry point for report, Checklist, and formal Drift handoffs.

Report and Checklist files must already be routed and saved under ``reports/``.
The default is a structural dry-run.  ``--write`` rebuilds derived dashboard
state but never commits, pushes, deploys, or makes an investment decision.
Formal Drift delegates to the established ``thesis_drift_handoff.py`` contract.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_investment_dashboard as dashboard  # noqa: E402


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


def inspect_report(root: Path, path: Path, kind: str) -> dict[str, Any]:
    registry = _registry(root)
    if kind == "checklist":
        record = dashboard.checklist_record(path, root, registry)
        if record is None:
            raise ValueError("file is not a recognizable standalone investment Checklist")
    else:
        overrides = dashboard.load_json(
            root / "data" / "investment-dashboard" / "overrides.json",
            {"schema_version": 1, "reports": {}, "companies": {}},
        )
        record = dashboard.candidate_record(path, root, registry, overrides)
        if record is None or not dashboard.is_company_equity(record):
            raise ValueError("file is not a recognizable individual-company main report")
        if dashboard.is_post_buy_tracking_report(record):
            raise ValueError("post-buy tracking reports must use thesis-tracker, not report handoff")
    if not record.get("ticker"):
        raise ValueError("report ticker could not be resolved")
    if not record.get("data_cutoff"):
        raise ValueError("report has no reliable data cutoff")
    return record


def _validate_state(root: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(root / "tools" / "validate_decision_state.py"), "--repo-root", str(root)],
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
    result = {
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
    if not args.write:
        return result
    built = dashboard.build_dashboard(root)
    _validate_state(root)
    result["completed"].extend(["dashboard_build", "decision_state_validation"])
    result["dashboard_effect"] = (
        f"Rebuilt {built.get('decision_count')} company decisions; derived state reflects {relative}."
    )
    if args.command == "report":
        result["next_skill"] = "Review Dashboard action guidance; run a specialist Skill only if it becomes actionable."
    else:
        result["next_skill"] = "Review Checklist result and current action guidance; purchase remains a human decision."
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
