#!/usr/bin/env python3
"""Validate the generated structured dashboard state contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import decision_state  # noqa: E402
import drift_scan_state  # noqa: E402


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    data = args.repo_root.resolve() / "data" / "investment-dashboard"
    try:
        rules = load(data / "decision_rules.json")
        state = load(data / "company_state.json")
        technical = load(data / "technical_latest.json")
        checklist = load(data / "checklist_states.json")
        event = load(data / "event_radar.json")
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    errors = decision_state.validate_payloads({"rules": rules, "state": state})
    scan_path = data / drift_scan_state.RELATIVE_PATH.name
    scan = None
    scan_stale_baselines = []
    if scan_path.exists():
        try:
            scan = drift_scan_state.load(scan_path, repo_root=args.repo_root.resolve())
            for ticker, record in (scan.get("companies") or {}).items():
                report = args.repo_root.resolve() / str(record.get("baseline_report") or "")
                try:
                    if report.is_file() and decision_state.canonical_report_hash(
                        {"report_path": record.get("baseline_report")}, args.repo_root.resolve()
                    ) != record.get("baseline_report_sha256"):
                        scan_stale_baselines.append(ticker)
                except OSError:
                    scan_stale_baselines.append(ticker)
        except ValueError as error:
            errors.append(str(error))
    if technical.get("schema_version") != decision_state.SCHEMA_VERSION:
        errors.append("technical_latest schema_version")
    if checklist.get("schema_version") != decision_state.SCHEMA_VERSION:
        errors.append("checklist_states schema_version")
    if event.get("schema_version") != 1:
        errors.append("event_radar schema_version")
    state_tickers = {item.get("ticker") for item in state.get("companies", [])}
    rule_tickers = {item.get("ticker") for item in rules.get("companies", [])}
    if state_tickers != rule_tickers:
        errors.append("company/rule ticker sets differ")
    if errors:
        print(json.dumps({"status": "fail", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({
        "status": "ok",
        "company_count": state.get("company_count"),
        "rule_count": rules.get("rule_count"),
        "event_company_count": event.get("company_count"),
        "drift_scan_record_count": len((scan or {}).get("companies", {})),
        "drift_scan_stale_baseline_count": len(scan_stale_baselines),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
