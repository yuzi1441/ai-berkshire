#!/usr/bin/env python3
"""Resumable local control plane for Codex-client Light Thesis reviews.

The script prepares immutable evidence packages, validates model results that
were supplied by the current Codex client, and delegates every authority write
to ``light_thesis_signals.upsert``.  It never invokes a model or provider.
Run workspaces live under the ignored ``local/`` tree and are not authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import light_thesis_evidence
import light_thesis_signals


RUN_SCHEMA_VERSION = 1
PACKAGE_SCHEMA_VERSION = 1
WORKSPACE_ROOT = Path("local/light-thesis-runs")
STATE_PATH = Path("data/investment-dashboard/company_state.json")
SIGNALS = frozenset(light_thesis_signals.SIGNALS)
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}")
TICKER_RE = re.compile(r"[A-Z0-9._-]{1,32}")


class WorkflowError(ValueError):
    """A fail-closed workflow contract violation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"expected JSON object: {path}")
    return value


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _save_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _workspace(repo_root: Path, run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise WorkflowError("invalid run_id")
    return repo_root.resolve() / WORKSPACE_ROOT / run_id


def _ticker_filename(ticker: str) -> str:
    ticker = str(ticker or "").strip().upper()
    if not TICKER_RE.fullmatch(ticker):
        raise WorkflowError(f"invalid ticker: {ticker!r}")
    return f"{ticker}.json"


def eligible_companies(repo_root: Path) -> list[dict[str, Any]]:
    state = _read_json(repo_root / STATE_PATH)
    rows = [
        row
        for row in state.get("companies") or []
        if isinstance(row, dict)
        and row.get("market") == "A股"
        and row.get("lifecycle") == "WATCH"
    ]
    return sorted(rows, key=lambda row: str(row.get("ticker") or ""))


def eligible_set_fingerprint(rows: list[dict[str, Any]]) -> str:
    return _sha(
        [
            {
                "ticker": row.get("ticker"),
                "lifecycle": row.get("lifecycle"),
                "canonical_report": row.get("canonical_report"),
                "canonical_report_sha256": row.get("canonical_report_sha256"),
            }
            for row in rows
        ]
    )


def freeze_package(raw: dict[str, Any]) -> dict[str, Any]:
    """Remove execution metadata and content-address the exact model input."""
    light_thesis_evidence.validate_package(raw)
    package = {
        key: raw.get(key)
        for key in (
            "schema_version",
            "purpose",
            "ticker",
            "company",
            "market",
            "lifecycle",
            "baseline_report_path",
            "baseline_report_sha256",
            "baseline_cutoff",
            "baseline_cutoff_provenance",
            "input_status",
            "evidence_items",
            "latest_evidence_at",
            "evidence_fingerprint",
            "review_contract",
        )
    }
    package["package_schema_version"] = PACKAGE_SCHEMA_VERSION
    package["package_fingerprint"] = _sha(package)
    validate_frozen_package(package)
    return package


def _validate_package_company(package: dict[str, Any], company: dict[str, Any]) -> None:
    expected = {
        "ticker": str(company.get("ticker") or "").upper(),
        "market": "A股",
        "lifecycle": "WATCH",
        "baseline_report_path": company.get("canonical_report"),
        "baseline_report_sha256": company.get("canonical_report_sha256"),
    }
    if {key: package.get(key) for key in expected} != expected:
        raise WorkflowError("prepared package does not match current company baseline")


def validate_frozen_package(package: dict[str, Any]) -> None:
    if package.get("package_schema_version") != PACKAGE_SCHEMA_VERSION:
        raise WorkflowError("invalid package_schema_version")
    expected = _sha({key: value for key, value in package.items() if key != "package_fingerprint"})
    if package.get("package_fingerprint") != expected:
        raise WorkflowError("package_fingerprint mismatch")
    try:
        light_thesis_evidence.validate_package(package)
    except light_thesis_evidence.EvidenceError as exc:
        raise WorkflowError(str(exc)) from exc


def _new_manifest(
    *, run_id: str, rows: list[dict[str, Any]], model: str, reasoning_effort: str
) -> dict[str, Any]:
    if not model.strip() or reasoning_effort not in EFFORTS:
        raise WorkflowError("operator-declared model and valid reasoning effort are required")
    return {
        "run_schema_version": RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "MODEL_STEP_PENDING_CODEX_CLIENT",
        "started_at": _now(),
        "completed_at": None,
        "operator_declared_model": model.strip(),
        "operator_declared_reasoning": reasoning_effort,
        "execution_surface": "codex_client",
        "script_did_not_invoke_model": True,
        "eligible_ticker_set": [row.get("ticker") for row in rows],
        "eligible_set_fingerprint": eligible_set_fingerprint(rows),
        "eligible_count": len(rows),
        "prepared_count": 0,
        "pending_count": len(rows),
        "validated_count": 0,
        "applied_count": 0,
        "failed_count": 0,
        "complete": False,
        "tickers": {},
    }


def _refresh_counts(manifest: dict[str, Any]) -> None:
    items = list((manifest.get("tickers") or {}).values())
    manifest["prepared_count"] = sum(item.get("package_status") == "prepared" for item in items)
    manifest["validated_count"] = sum(item.get("validation_status") == "valid" for item in items)
    manifest["applied_count"] = sum(item.get("apply_status") == "applied" for item in items)
    manifest["failed_count"] = sum(
        item.get("validation_status") == "failed" or item.get("apply_status") == "failed"
        for item in items
    )
    manifest["pending_count"] = manifest["eligible_count"] - manifest["applied_count"]
    manifest["complete"] = bool(
        manifest.get("status") == "COMPLETE"
        and manifest["applied_count"] == manifest["eligible_count"]
        and manifest["failed_count"] == 0
    )


def prepare(
    repo_root: Path,
    run_id: str,
    *,
    model: str,
    reasoning_effort: str,
    write: bool = False,
    package_preparer: Callable[[Path, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    rows = eligible_companies(repo_root)
    manifest = _new_manifest(
        run_id=run_id, rows=rows, model=model, reasoning_effort=reasoning_effort
    )
    package_preparer = package_preparer or light_thesis_evidence.prepare_for_ticker
    packages: dict[str, dict[str, Any]] = {}
    blocked: list[dict[str, str]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        try:
            frozen = freeze_package(package_preparer(repo_root, ticker))
            _validate_package_company(frozen, row)
            packages[ticker] = frozen
            manifest["tickers"][ticker] = {
                "package_fingerprint": packages[ticker]["package_fingerprint"],
                "package_status": "prepared",
                "result_status": "pending",
                "validation_status": "pending",
                "apply_status": "pending",
                "error_code": None,
            }
        except (WorkflowError, light_thesis_evidence.EvidenceError, ValueError) as exc:
            blocked.append({"ticker": ticker, "error": str(exc)})
            manifest["tickers"][ticker] = {
                "package_fingerprint": None,
                "package_status": "blocked",
                "result_status": "pending",
                "validation_status": "pending",
                "apply_status": "pending",
                "error_code": "PREPARE_FAILED",
            }
    _refresh_counts(manifest)
    preview = {
        "mode": "write" if write else "dry_run",
        "run_id": run_id,
        "proposed_workspace": str(_workspace(repo_root, run_id)),
        "eligible_count": len(rows),
        "eligible_set_fingerprint": manifest["eligible_set_fingerprint"],
        "prepared_count": len(packages),
        "blocked_count": len(blocked),
        "blocked": blocked,
        "authority_written": False,
        "script_did_not_invoke_model": True,
    }
    if not write:
        return preview
    workspace = _workspace(repo_root, run_id)
    if workspace.exists():
        raise WorkflowError(f"run workspace already exists: {workspace}")
    for ticker, package in packages.items():
        _save_new(workspace / "packages" / _ticker_filename(ticker), package)
    (workspace / "results").mkdir(parents=True, exist_ok=True)
    (workspace / "validation").mkdir(parents=True, exist_ok=True)
    _save_new(workspace / "run_manifest.json", manifest)
    _save_new(workspace / "apply_state.json", {"applied": {}, "failed": {}})
    return preview


def _load_run(repo_root: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    workspace = _workspace(repo_root, run_id)
    manifest = _read_json(workspace / "run_manifest.json")
    if manifest.get("run_id") != run_id or manifest.get("run_schema_version") != RUN_SCHEMA_VERSION:
        raise WorkflowError("invalid run manifest")
    if manifest.get("script_did_not_invoke_model") is not True:
        raise WorkflowError("manifest model provenance is invalid")
    return workspace, manifest


def _validate_current_universe(repo_root: Path, manifest: dict[str, Any]) -> None:
    current = eligible_companies(repo_root)
    if eligible_set_fingerprint(current) != manifest.get("eligible_set_fingerprint"):
        raise WorkflowError("eligible universe changed; reprepare required")


def validate_result(
    package: dict[str, Any],
    result: dict[str, Any],
    *,
    expected_model: str | None = None,
    expected_reasoning: str | None = None,
) -> dict[str, Any]:
    validate_frozen_package(package)
    required_text = (
        "ticker", "package_fingerprint", "baseline_sha256", "evidence_fingerprint",
        "signal", "summary", "checked_at", "model", "reasoning_effort",
        "execution_surface", "provenance",
    )
    missing = [field for field in required_text if not str(result.get(field) or "").strip()]
    if missing:
        raise WorkflowError("missing result fields: " + ", ".join(missing))
    if str(result["ticker"]).upper() != package.get("ticker"):
        raise WorkflowError("result ticker mismatch")
    if result["package_fingerprint"] != package.get("package_fingerprint"):
        raise WorkflowError("result package_fingerprint mismatch")
    if result["baseline_sha256"] != package.get("baseline_report_sha256"):
        raise WorkflowError("result baseline_sha256 mismatch")
    if result["evidence_fingerprint"] != package.get("evidence_fingerprint"):
        raise WorkflowError("result evidence_fingerprint mismatch")
    if result["signal"] not in SIGNALS:
        raise WorkflowError("invalid result signal")
    if result["execution_surface"] != "codex_client":
        raise WorkflowError("execution_surface must be codex_client")
    if result["provenance"] != "MODEL_RESULT_PROVIDED_BY_CODEX_CLIENT":
        raise WorkflowError("invalid model result provenance")
    if expected_model is not None and result["model"] != expected_model:
        raise WorkflowError("result model does not match operator declaration")
    if expected_reasoning is not None and result["reasoning_effort"] != expected_reasoning:
        raise WorkflowError("result reasoning does not match operator declaration")
    try:
        datetime.fromisoformat(str(result["checked_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkflowError("invalid checked_at") from exc
    refs = result.get("material_evidence_refs")
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise WorkflowError("material_evidence_refs must be an evidence_id list")
    if len(refs) != len(set(refs)):
        raise WorkflowError("material_evidence_refs must be unique")
    evidence_ids = {item.get("evidence_id") for item in package.get("evidence_items") or []}
    missing_refs = sorted(set(refs) - evidence_ids)
    if missing_refs:
        raise WorkflowError("unknown material_evidence_refs: " + ", ".join(missing_refs))
    if result["signal"] != "insufficient_evidence" and not refs:
        raise WorkflowError("material_evidence_refs required for substantive signal")
    return result


def _current_package(
    repo_root: Path,
    ticker: str,
    package_preparer: Callable[[Path, str], dict[str, Any]] | None,
) -> dict[str, Any]:
    preparer = package_preparer or light_thesis_evidence.prepare_for_ticker
    return freeze_package(preparer(repo_root, ticker))


def _record_from_result(package: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    by_id = {item["evidence_id"]: item for item in package.get("evidence_items") or []}
    material = []
    for evidence_id in result["material_evidence_refs"]:
        item = by_id[evidence_id]
        material.append({
            "summary": item["concise_fact"],
            "source": item["source"],
            "date": item["date"],
            "evidence_id": evidence_id,
            "source_identity": item["source_identity"],
            "content_sha256": item["content_sha256"],
        })
    return {
        "ticker": package["ticker"],
        "lifecycle_at_review": "WATCH",
        "baseline_report_path": package["baseline_report_path"],
        "baseline_report_sha256": package["baseline_report_sha256"],
        "checked_at": result["checked_at"],
        "evidence_fingerprint": package["evidence_fingerprint"],
        "signal": result["signal"],
        "summary": result["summary"],
        "material_evidence": material,
        "model": result["model"],
        "provider": "local_codex_client",
        "provenance": "MODEL_RESULT_PROVIDED_BY_CODEX_CLIENT",
    }


def _verify_authority_record(repo_root: Path, record: dict[str, Any]) -> None:
    payload = light_thesis_signals.load(repo_root / light_thesis_signals.RELATIVE_PATH)
    saved = (payload.get("companies") or {}).get(record["ticker"])
    identity = (
        record["baseline_report_sha256"], record["evidence_fingerprint"], record["signal"]
    )
    if not isinstance(saved, dict) or (
        saved.get("baseline_report_sha256"),
        saved.get("evidence_fingerprint"),
        saved.get("signal"),
    ) != identity:
        raise WorkflowError("authority write verification failed")


def validate_run(repo_root: Path, run_id: str, *, write: bool = True) -> dict[str, Any]:
    workspace, manifest = _load_run(repo_root, run_id)
    failures: list[dict[str, str]] = []
    for ticker, state in manifest["tickers"].items():
        if state.get("package_status") != "prepared" or state.get("apply_status") == "applied":
            continue
        result_path = workspace / "results" / _ticker_filename(ticker)
        if not result_path.is_file():
            state["result_status"] = "pending"
            continue
        state["result_status"] = "provided"
        try:
            package = _read_json(workspace / "packages" / _ticker_filename(ticker))
            validate_result(
                package,
                _read_json(result_path),
                expected_model=manifest["operator_declared_model"],
                expected_reasoning=manifest["operator_declared_reasoning"],
            )
            state["validation_status"] = "valid"
            state["error_code"] = None
            validation = {"ticker": ticker, "status": "valid"}
        except (WorkflowError, ValueError) as exc:
            state["validation_status"] = "failed"
            state["error_code"] = "RESULT_INVALID"
            validation = {"ticker": ticker, "status": "failed", "error": str(exc)}
            failures.append({"ticker": ticker, "error": str(exc)})
        if write:
            _write_json_atomic(workspace / "validation" / _ticker_filename(ticker), validation)
    _refresh_counts(manifest)
    if any(item.get("result_status") == "provided" for item in manifest["tickers"].values()):
        manifest["status"] = "MODEL_RESULT_PROVIDED_BY_CODEX_CLIENT"
    if write:
        _write_json_atomic(workspace / "run_manifest.json", manifest)
    return {"run_id": run_id, "validated": manifest["validated_count"], "failed": failures}


def apply_run(
    repo_root: Path,
    run_id: str,
    *,
    write: bool,
    package_preparer: Callable[[Path, str], dict[str, Any]] | None = None,
    upsert: Callable[[Path, dict[str, Any]], str] | None = None,
) -> dict[str, Any]:
    if not write:
        raise WorkflowError("apply requires --write")
    repo_root = repo_root.resolve()
    validate_run(repo_root, run_id, write=True)
    workspace, manifest = _load_run(repo_root, run_id)
    _validate_current_universe(repo_root, manifest)
    apply_state = _read_json(workspace / "apply_state.json")
    failures: list[dict[str, str]] = []
    upsert = upsert or light_thesis_signals.upsert
    for ticker, state in manifest["tickers"].items():
        if state.get("apply_status") == "applied" or state.get("validation_status") != "valid":
            continue
        try:
            package = _read_json(workspace / "packages" / _ticker_filename(ticker))
            result = _read_json(workspace / "results" / _ticker_filename(ticker))
            validate_result(
                package,
                result,
                expected_model=manifest["operator_declared_model"],
                expected_reasoning=manifest["operator_declared_reasoning"],
            )
            current = _current_package(repo_root, ticker, package_preparer)
            if current["package_fingerprint"] != package["package_fingerprint"]:
                raise WorkflowError("current baseline/evidence changed; reprepare required")
            record = _record_from_result(package, result)
            outcome = upsert(repo_root, record)
            if upsert is light_thesis_signals.upsert:
                _verify_authority_record(repo_root, record)
            state.update(apply_status="applied", error_code=None)
            apply_state.setdefault("applied", {})[ticker] = {"outcome": outcome, "at": _now()}
            apply_state.setdefault("failed", {}).pop(ticker, None)
        except (WorkflowError, ValueError, OSError) as exc:
            state.update(apply_status="failed", error_code="APPLY_FAILED")
            apply_state.setdefault("failed", {})[ticker] = {"error": str(exc), "at": _now()}
            failures.append({"ticker": ticker, "error": str(exc)})
        _refresh_counts(manifest)
        _write_json_atomic(workspace / "apply_state.json", apply_state)
        _write_json_atomic(workspace / "run_manifest.json", manifest)
    return {"run_id": run_id, "applied": manifest["applied_count"], "failed": failures}


def status(repo_root: Path, run_id: str) -> dict[str, Any]:
    _, manifest = _load_run(repo_root.resolve(), run_id)
    _refresh_counts(manifest)
    return {
        key: manifest.get(key)
        for key in (
            "run_id", "status", "eligible_count", "prepared_count", "pending_count",
            "validated_count", "applied_count", "failed_count", "complete",
            "execution_surface", "script_did_not_invoke_model",
        )
    }


def finalize(
    repo_root: Path,
    run_id: str,
    *,
    write: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    if not write:
        raise WorkflowError("finalize requires --write")
    repo_root = repo_root.resolve()
    workspace, manifest = _load_run(repo_root, run_id)
    _validate_current_universe(repo_root, manifest)
    _refresh_counts(manifest)
    if manifest["applied_count"] != manifest["eligible_count"] or manifest["failed_count"]:
        raise WorkflowError("run has pending or failed tickers and cannot be finalized")
    runner = runner or subprocess.run
    commands = [
        [sys.executable, str(repo_root / "tools/build_investment_dashboard.py"), "--repo-root", str(repo_root)],
        [sys.executable, str(repo_root / "tools/validate_decision_state.py"), "--repo-root", str(repo_root)],
        [sys.executable, str(repo_root / "tools/light_thesis_signals.py"), "--repo-root", str(repo_root), "validate"],
    ]
    for command in commands:
        runner(command, cwd=repo_root, check=True, text=True, capture_output=True)
    manifest.update(
        status="COMPLETE",
        complete=True,
        completed_at=_now(),
    )
    _write_json_atomic(workspace / "run_manifest.json", manifest)
    return {"run_id": run_id, "complete": True, "build_and_validators": "pass"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--run-id", required=True)
    prepare_parser.add_argument("--model", required=True)
    prepare_parser.add_argument("--reasoning-effort", required=True, choices=EFFORTS)
    prepare_parser.add_argument("--write", action="store_true")
    for name in ("status", "validate", "apply", "finalize"):
        command = commands.add_parser(name)
        command.add_argument("--run", required=True)
        if name in {"apply", "finalize"}:
            command.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if args.command == "prepare":
        result = prepare(root, args.run_id, model=args.model,
                         reasoning_effort=args.reasoning_effort, write=args.write)
    elif args.command == "status":
        result = status(root, args.run)
    elif args.command == "validate":
        result = validate_run(root, args.run)
    elif args.command == "apply":
        result = apply_run(root, args.run, write=args.write)
    else:
        result = finalize(root, args.run, write=args.write)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
