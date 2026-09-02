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
import post_buy_tracking  # noqa: E402
import rule_lifecycle  # noqa: E402


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取 JSON: {path}: {error}") from error


def _save(path: Path, payload: dict) -> None:
    decision_state.write_json(path, payload)


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
        path = Path(raw)
        resolved = path if path.is_absolute() else root / path
        if not resolved.is_file():
            print(f"FAIL: facts source 不存在: {raw}", file=sys.stderr)
            return 1
        sources.append(resolved.relative_to(root).as_posix() if resolved.is_relative_to(root) else str(resolved))

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
    if args.dry_run:
        original = _original_thesis_snapshot(root, ticker, timestamp=record["last_checked"], write=False) if args.mode == "holding" else None
        print(json.dumps({"status": "dry_run", "ticker": ticker, "mode": args.mode, "record": record, "original_buy_thesis": original}, ensure_ascii=False, indent=2))
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
    _save(drift_path, payload)
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
