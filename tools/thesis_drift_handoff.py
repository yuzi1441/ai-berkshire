#!/usr/bin/env python3
"""Validate a completed thesis-drift result and hand it to the dashboard.

The thesis-drift Skill remains responsible for comparing the thesis with the
latest facts.  This small, explicit handoff only validates that result against
the current Company State and existing fact sources, freezes a Holding's
purchase-time baseline, writes the established ``drift_states.json`` record,
and rebuilds the dashboard.  A non-unchanged result also invokes the targeted
Rule lifecycle synchronizer; an unchanged result never mutates Rule content.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_investment_dashboard  # noqa: E402
import decision_state  # noqa: E402
import drift_provenance  # noqa: E402
import drift_scan_state  # noqa: E402
import post_buy_tracking  # noqa: E402
import rule_lifecycle  # noqa: E402


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取 JSON: {path}: {error}") from error


def _save(path: Path, payload: dict) -> None:
    decision_state.write_json(path, payload)


def _watch_scan_checkpoint(
    root: Path,
    data: Path,
    company: dict,
    record: dict,
) -> tuple[Path, dict] | None:
    """Bind a completed WATCH review to the exact current Drift trigger.

    ``drift_states.json`` stores the conclusion, while
    ``drift_scan_state.json`` stores the evidence/baseline fingerprint that
    conclusion covers.  Persisting only the former leaves the checkpoint
    stale and makes Action Guidance immediately request the same review again.
    """
    if record.get("mode") != "watch":
        return None
    scan = company.get("drift_scan") or {}
    trigger_fingerprint = (
        scan.get("current_trigger_fingerprint")
        or scan.get("trigger_fingerprint")
    )
    baseline_report = company.get("canonical_report")
    baseline_report_sha256 = company.get("canonical_report_sha256")
    if not baseline_report or not baseline_report_sha256:
        raise ValueError("WATCH Drift handoff 缺少当前 canonical report 基线")
    if not drift_scan_state.is_sha256(trigger_fingerprint):
        raise ValueError("WATCH Drift handoff 缺少当前 trigger fingerprint")

    path = data / drift_scan_state.RELATIVE_PATH.name
    payload = _load(path) if path.is_file() else {
        "schema_version": drift_scan_state.SCHEMA_VERSION,
        "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
        "description": "Durable WATCH thesis-drift review checkpoints.",
        "companies": {},
    }
    if (
        payload.get("schema_version") != drift_scan_state.SCHEMA_VERSION
        or payload.get("trigger_fingerprint_version")
        != drift_scan_state.FINGERPRINT_VERSION
        or not isinstance(payload.get("companies"), dict)
    ):
        raise ValueError(f"Drift scan checkpoint schema 无法识别: {path}")
    ticker = str(company.get("ticker") or "").upper()
    payload["companies"][ticker] = {
        "ticker": ticker,
        "company": company.get("company"),
        "market": company.get("market"),
        "mode": "watch",
        "checked_at": record["last_checked"],
        "result": record["direction"],
        "baseline_report": baseline_report,
        "baseline_report_sha256": baseline_report_sha256,
        "trigger_fingerprint_version": drift_scan_state.FINGERPRINT_VERSION,
        "trigger_fingerprint": trigger_fingerprint,
        "source": "thesis-drift-handoff",
    }
    errors = drift_scan_state.validate_payload(payload, repo_root=root)
    if errors:
        raise ValueError("Drift scan checkpoint 无效: " + "; ".join(errors))
    return path, payload


def _original_thesis_snapshot(
    root: Path,
    ticker: str,
    *,
    timestamp: str,
    write: bool,
) -> dict:
    """Capture once, then only verify the frozen purchase-time thesis.

    The current thesis report is allowed to evolve.  The original snapshot is
    an append-safe baseline for Holding Drift and is never overwritten by this
    handoff command.
    """
    root = root.resolve()
    data = root / "data" / "investment-dashboard"
    tracking_path = data / decision_state.POST_BUY_RELATIVE.name
    tracking = _load(tracking_path) if tracking_path.is_file() else {"positions": {}}
    position = (tracking.get("positions") or {}).get(ticker)
    if not isinstance(position, dict):
        return {"status": "missing_position", "ticker": ticker}
    result = post_buy_tracking.freeze_original_buy_thesis(
        root,
        position,
        timestamp=timestamp,
        write=write,
        provenance="holding_drift_backfill",
        backfilled=True,
    )
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker", help="股票代码，例如 301666.SZ")
    parser.add_argument("--mode", choices=("watch", "holding"), required=True)
    parser.add_argument(
        "--direction",
        choices=decision_state.DRIFT_DIRECTIONS,
        required=True,
    )
    parser.add_argument(
        "--severity",
        choices=decision_state.DRIFT_SEVERITIES,
        default="none",
    )
    parser.add_argument("--summary", required=True)
    parser.add_argument("--next-review")
    parser.add_argument(
        "--facts-source",
        nargs="+",
        required=True,
        help="本次 Drift 实际读取的报告或结构化事实文件，必须存在",
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    write_group = parser.add_mutually_exclusive_group(required=True)
    write_group.add_argument("--write", action="store_true")
    write_group.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.repo_root.resolve()
    data = root / "data" / "investment-dashboard"
    ticker = args.ticker.upper()
    state_payload = _load(data / decision_state.STATE_RELATIVE.name)
    company = next(
        (item for item in state_payload.get("companies", []) if str(item.get("ticker", "")).upper() == ticker),
        None,
    )
    if company is None:
        print(f"FAIL: Company State 中不存在 {ticker}", file=sys.stderr)
        return 1
    expected_mode = "holding" if company.get("lifecycle") == "HOLDING" else "watch" if company.get("lifecycle") == "WATCH" else None
    if expected_mode != args.mode:
        print(
            f"FAIL: {ticker} 的 lifecycle={company.get('lifecycle')} 与 mode={args.mode} 不匹配",
            file=sys.stderr,
        )
        return 1
    sources: list[str] = []
    for raw in args.facts_source:
        try:
            source = drift_provenance.normalize_facts_source(root, raw)
        except ValueError as error:
            print(f"FAIL: {error}", file=sys.stderr)
            return 1
        sources.append(source)

    record = {
        "direction": args.direction,
        "severity": args.severity,
        "summary": args.summary,
        "last_checked": datetime.now().astimezone().isoformat(timespec="seconds"),
        "next_review": args.next_review,
        "source": "thesis-drift-handoff",
        "facts_sources": sources,
        "mode": args.mode,
    }
    try:
        watch_checkpoint = _watch_scan_checkpoint(root, data, company, record)
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if args.dry_run:
        original = _original_thesis_snapshot(root, ticker, timestamp=record["last_checked"], write=False) if args.mode == "holding" else None
        print(json.dumps({
            "status": "dry_run",
            "ticker": ticker,
            "mode": args.mode,
            "record": record,
            "drift_scan_checkpoint": (
                watch_checkpoint[1]["companies"][ticker]
                if watch_checkpoint is not None else None
            ),
            "original_buy_thesis": original,
        }, ensure_ascii=False, indent=2))
        return 0

    original = _original_thesis_snapshot(root, ticker, timestamp=record["last_checked"], write=True) if args.mode == "holding" else None
    if args.mode == "holding" and original.get("status") in {"missing_position", "missing_thesis_report_path", "missing_thesis_report"}:
        print(json.dumps({"status": "blocked", "ticker": ticker, "original_buy_thesis": original}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    drift_path = data / decision_state.DRIFT_RELATIVE.name
    payload = _load(drift_path) if drift_path.is_file() else {"schema_version": 1, "companies": {}}
    if payload.get("schema_version", 1) != 1 or not isinstance(payload.get("companies"), dict):
        print(f"FAIL: Drift state schema 无法识别: {drift_path}", file=sys.stderr)
        return 1
    payload["schema_version"] = 1
    previous_record = payload["companies"].get(ticker) or {}
    history = list(previous_record.get("review_history") or []) if isinstance(previous_record, dict) else []
    history.append(dict(record))
    record["review_history"] = history
    payload["companies"][ticker] = record
    provenance_errors = drift_provenance.validate_drift_facts_sources(root, payload)
    if provenance_errors:
        print(
            json.dumps({"status": "blocked", "errors": provenance_errors}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1
    _save(drift_path, payload)
    if watch_checkpoint is not None:
        _save(*watch_checkpoint)
    rule_sync = {"status": "not_requested", "reason": "unchanged drift does not mutate Rule content"}
    if args.direction != "unchanged":
        rule_sync = rule_lifecycle.sync_decision_rules(root, tickers=[ticker], write=True, rebuild_dashboard=False)
    board = build_investment_dashboard.build_dashboard(root)
    updated = next((item for item in board.get("decisions", []) if str(item.get("ticker", "")).upper() == ticker), None)
    print(json.dumps({
        "status": "written",
        "ticker": ticker,
        "mode": args.mode,
        "drift": record,
        "original_buy_thesis": original,
        "rule_sync": rule_sync,
        "dashboard_lifecycle": (updated or {}).get("lifecycle"),
        "dashboard_next_action": (updated or {}).get("next_action"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
