#!/usr/bin/env python3
"""Validate the generated structured dashboard state contracts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import decision_state  # noqa: E402
import drift_scan_state  # noqa: E402
import drift_provenance  # noqa: E402
import holding_research_reviews  # noqa: E402
import financial_facts  # noqa: E402


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error


def git_tracked(root: Path, relative_path: str) -> bool:
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative_path],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def formal_asset_paths(data: Path) -> set[str]:
    paths: set[str] = set()
    catalog_path = data / "reports_catalog.json"
    if catalog_path.is_file():
        for record in load(catalog_path).get("records", []):
            if isinstance(record, dict) and record.get("report_path"):
                paths.add(str(record["report_path"]))
    scan_path = data / "drift_scan_state.json"
    if scan_path.is_file():
        payload = load(scan_path)
        companies = payload.get("companies", payload)
        for record in companies.values() if isinstance(companies, dict) else []:
            if isinstance(record, dict) and record.get("baseline_report"):
                paths.add(str(record["baseline_report"]))
    drift_path = data / "drift_states.json"
    if drift_path.is_file():
        for record in (load(drift_path).get("companies") or {}).values():
            if not isinstance(record, dict):
                continue
            for source in record.get("facts_sources") or []:
                if isinstance(source, str) and not source.startswith(("http://", "https://")):
                    paths.add(source)
    holding_path = data / holding_research_reviews.RELATIVE_PATH.name
    if holding_path.is_file():
        for review in (load(holding_path).get("reviews") or {}).values():
            if isinstance(review, dict) and review.get("report_path"):
                paths.add(str(review["report_path"]))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--require-tracked-assets", action="store_true")
    parser.add_argument(
        "--tracked-root", type=Path, default=None,
        help="Git checkout used for tracked-asset checks when validating an assembled release.",
    )
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
    financial_path = data / financial_facts.RELATIVE_PATH.name
    if financial_path.is_file():
        try:
            errors.extend(financial_facts.validate_payload(load(financial_path)))
        except ValueError as error:
            errors.append(str(error))
    if technical.get("schema_version") != decision_state.SCHEMA_VERSION:
        errors.append("technical_latest schema_version")
    if checklist.get("schema_version") != decision_state.SCHEMA_VERSION:
        errors.append("checklist_states schema_version")
    if event.get("schema_version") != 1:
        errors.append("event_radar schema_version")
    drift_path = data / "drift_states.json"
    if drift_path.is_file():
        try:
            errors.extend(drift_provenance.validate_drift_facts_sources(
                args.repo_root.resolve(), load(drift_path)
            ))
        except ValueError as error:
            errors.append(str(error))
    holding_path = data / holding_research_reviews.RELATIVE_PATH.name
    if holding_path.is_file():
        try:
            errors.extend(
                holding_research_reviews.validate_payload(load(holding_path), repo_root=args.repo_root.resolve())
            )
        except ValueError as error:
            errors.append(str(error))
    if args.require_tracked_assets:
        tracked_root = (args.tracked_root or args.repo_root).resolve()
        for relative_path in sorted(formal_asset_paths(data)):
            candidate = args.repo_root.resolve() / relative_path
            if not candidate.is_file():
                errors.append(f"formal asset missing: {relative_path}")
            elif not git_tracked(tracked_root, relative_path):
                errors.append(f"formal asset is not Git tracked: {relative_path}")
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
