#!/usr/bin/env python3
"""Import the reviewed WATCH-universe audit into the durable scan layer.

This is an explicit migration command.  It reads the existing research
artifact, verifies that its Main Report identities still match the current
Company State, and writes only ``drift_scan_state.json`` when ``--write`` is
provided.  It never writes formal ``drift_states.json`` records.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import decision_state  # noqa: E402
import drift_scan_state  # noqa: E402
import event_radar  # noqa: E402
from source_hash import canonical_file_sha256  # noqa: E402


BATCH_ID = "a-share-watch-full-drift-20260903-v2"
EXPECTED_DISTRIBUTION = {"improved": 17, "unchanged": 40, "weakened": 14, "unknown": 5}


def _load(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label}: {path}: {error}") from error


def _state_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("companies")
    if not isinstance(rows, list):
        raise ValueError("company_state companies must be a list")
    return [row for row in rows if isinstance(row, dict)]


def _event_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker")).upper(): row
        for row in payload.get("companies", [])
        if isinstance(row, dict) and row.get("ticker")
    }


def _report_hash(root: Path, report: str) -> str:
    path = (root / report).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"baseline report outside repository: {report}") from error
    if not path.is_file():
        raise ValueError(f"baseline report missing: {report}")
    return canonical_file_sha256(path)


def _current_state_by_ticker(root: Path) -> dict[str, dict[str, Any]]:
    payload = decision_state.load_strict_json(
        root / decision_state.STATE_RELATIVE, label="company_state"
    )
    return {
        str(row.get("ticker")).upper(): row
        for row in _state_rows(payload)
        if row.get("ticker")
    }


def build_checkpoint(root: Path, artifact_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = _load(artifact_path, "drift audit artifact")
    if not isinstance(artifact, dict):
        raise ValueError("drift audit artifact must be an object")
    companies = artifact.get("companies")
    if not isinstance(companies, list):
        raise ValueError("drift audit artifact companies must be a list")
    tickers = [str(item.get("ticker") or "").upper() for item in companies if isinstance(item, dict)]
    duplicates = sorted(ticker for ticker, count in Counter(tickers).items() if ticker and count > 1)
    if duplicates:
        raise ValueError(f"duplicate audit tickers: {duplicates}")
    if len(tickers) != 76 or len(set(tickers)) != 76:
        raise ValueError(f"audit target count must be 76, got {len(tickers)}")
    directions = Counter(str(item.get("direction") or "").lower() for item in companies if isinstance(item, dict))
    if dict(directions) != EXPECTED_DISTRIBUTION:
        raise ValueError(f"audit distribution mismatch: {dict(directions)}")

    current = _current_state_by_ticker(root)
    current_watch_tickers = {
        ticker
        for ticker, row in current.items()
        if row.get("market") == "A股" and row.get("lifecycle") == "WATCH"
    }
    event_payload = event_radar.build_event_radar(root, write=False)
    events = _event_rows(event_payload)
    records: dict[str, dict[str, Any]] = {}
    baseline_changed: list[str] = []
    for item in companies:
        if not isinstance(item, dict):
            raise ValueError("audit company record is not an object")
        ticker = str(item.get("ticker") or "").upper()
        state = current.get(ticker)
        if state is None:
            raise ValueError(f"audit ticker missing from current company_state: {ticker}")
        if state.get("market") != "A股":
            raise ValueError(f"audit ticker is not A股 in current state: {ticker}")
        report = str(state.get("canonical_report") or item.get("main_report_path") or "")
        artifact_report = str(item.get("main_report_path") or item.get("baseline_report") or "")
        artifact_hash = str(item.get("canonical_report_sha256") or "").lower()
        actual_hash = _report_hash(root, report)
        if report != artifact_report or actual_hash != artifact_hash:
            baseline_changed.append(ticker)
        evidence = item.get("current_evidence") or []
        evidence_hash = drift_scan_state.sha256_text(evidence)
        runtime_rules = (state.get("decision_rules") or {}).get("rules") or []
        event = events.get(ticker, {"state": "unknown", "source_status": "unavailable", "events": []})
        fingerprint = drift_scan_state.trigger_fingerprint(
            ticker,
            actual_hash,
            runtime_rules,
            event,
            research_evidence_sha256=evidence_hash,
        )
        records[ticker] = {
            "ticker": ticker,
            "company": item.get("company") or state.get("company"),
            "market": "A股",
            "mode": "watch",
            "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
            "result": str(item.get("direction") or "").lower(),
            "checked_at": str(artifact.get("generated_at") or artifact.get("as_of") or ""),
            "audit_as_of": artifact.get("as_of"),
            "baseline_report": report,
            "baseline_report_sha256": actual_hash,
            "trigger_fingerprint": fingerprint,
            "research_evidence_sha256": evidence_hash,
            "research_evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            "batch_id": BATCH_ID,
            "source": "full-watch-thesis-drift-audit",
            "research_status": item.get("research_status"),
        }
    if baseline_changed:
        raise ValueError("BASELINE_CHANGED_SINCE_AUDIT: " + ", ".join(sorted(baseline_changed)))

    audit_coverage = artifact.get("coverage") if isinstance(artifact.get("coverage"), dict) else {}
    payload = {
        "schema_version": drift_scan_state.SCHEMA_VERSION,
        "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
        "description": "WATCH thesis scan coverage; distinct from material formal Drift events.",
        "batch_id": BATCH_ID,
        "scope": {
            "market": "A股",
            "lifecycle": "WATCH",
            "target_count": len(records),
            "source_artifact": artifact_path.relative_to(root).as_posix()
            if artifact_path.is_relative_to(root)
            else str(artifact_path),
        },
        "coverage": {
            "scan_recorded": len(records),
            "result_distribution": dict(directions),
            "source_review_count": audit_coverage.get("review_count"),
            "source_review_count_equals_target_count": audit_coverage.get("review_count_equals_target_count"),
            "current_state_watch_count": len(current_watch_tickers),
            "current_state_uncovered_tickers": sorted(current_watch_tickers - set(records)),
        },
        "companies": records,
    }
    errors = drift_scan_state.validate_payload(payload, repo_root=root)
    if errors:
        raise ValueError("generated checkpoint invalid: " + "; ".join(errors))
    audit = {
        "artifact_target_count": len(records),
        "distribution": dict(directions),
        "baseline_valid": len(records),
        "baseline_changed": len(baseline_changed),
        "current_state_watch_count": sum(
            row.get("market") == "A股" and row.get("lifecycle") == "WATCH"
            for row in current.values()
        ),
        "current_state_target_difference": sorted(
            set(ticker for ticker, row in current.items() if row.get("market") == "A股" and row.get("lifecycle") == "WATCH")
            - set(records)
        ),
    }
    return payload, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=ROOT / "reports/thesis-drift-batch/A股-WATCH-全量论文漂移检测-20260903-v2.json",
    )
    parser.add_argument("--write", action="store_true", help="write drift_scan_state.json after validation")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    artifact = args.artifact.resolve()
    try:
        payload, audit = build_checkpoint(root, artifact)
        if args.write:
            decision_state.write_json(root / drift_scan_state.RELATIVE_PATH, payload)
        print(json.dumps({"status": "written" if args.write else "validated", **audit}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
