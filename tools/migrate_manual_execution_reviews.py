#!/usr/bin/env python3
"""Migrate the universe-wide human review file to independent per-stock records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import build_investment_dashboard as dashboard


ROOT = Path(__file__).resolve().parents[1]


def migrate(payload: dict[str, Any], decisions: list[dict[str, Any]], repo_root: Path) -> dict[str, Any]:
    if payload.get("schema_version") == 2:
        return payload
    if payload.get("schema_version") != 1:
        raise ValueError("manual review schema must be version 1 or 2")
    legacy = dashboard.legacy_manual_review_records(payload)
    reviews: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if decision.get("market") != "A股":
            continue
        ticker = str(decision.get("ticker") or "").upper()
        record = legacy.get(ticker)
        if not isinstance(record, dict):
            continue
        source_report = str(record.get("source_report") or payload.get("source_report") or "") or None
        snapshot = dashboard.manual_review_source_snapshot(decision, source_report, repo_root)
        reviews[ticker] = {
            **record,
            "reviewer": record.get("reviewer") or payload.get("reviewer") or "人工复核",
            "reviewed_at": record.get("reviewed_at") or payload.get("reviewed_at"),
            "price_as_of": record.get("price_as_of") or payload.get("price_as_of"),
            "source_report": source_report,
            "valid_until": dashboard.manual_review_valid_until(
                str(record.get("reviewed_at") or payload.get("reviewed_at") or "") or None,
                None,
                str((decision.get("checklist") or {}).get("next_review_date") or "") or None,
            ),
            "source_snapshot": snapshot,
            "source_fingerprint_sha256": dashboard.manual_review_fingerprint(snapshot),
        }
    return {
        "schema_version": 2,
        "status": payload.get("status") or "ready",
        "reviewer": payload.get("reviewer") or "人工复核",
        "reviewed_at": payload.get("reviewed_at"),
        "price_as_of": payload.get("price_as_of"),
        "source_report": payload.get("source_report"),
        "reviewed_count": len(reviews),
        "reviews": dict(sorted(reviews.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="validate and print counts without writing")
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    review_path = root / "data" / "investment-dashboard" / "manual_execution_reviews.json"
    board_path = root / "data" / "investment-dashboard" / "decision_board.json"
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    board = json.loads(board_path.read_text(encoding="utf-8"))
    migrated = migrate(payload, board.get("decisions") or [], root)
    a_shares = [
        item
        for item in board.get("decisions") or []
        if isinstance(item, dict) and item.get("market") == "A股"
    ]
    fingerprints_valid = 0
    missing_tickers: list[str] = []
    fingerprint_mismatches: list[str] = []
    for decision in a_shares:
        ticker = str(decision.get("ticker") or "").upper()
        review = (migrated.get("reviews") or {}).get(ticker)
        if not isinstance(review, dict):
            missing_tickers.append(ticker)
            continue
        snapshot = dashboard.manual_review_source_snapshot(
            decision, str(review.get("source_report") or "") or None, root
        )
        current = dashboard.manual_review_fingerprint(snapshot)
        if current == review.get("source_fingerprint_sha256"):
            fingerprints_valid += 1
        else:
            fingerprint_mismatches.append(ticker)
    if not arguments.check:
        dashboard.write_json(review_path, migrated)
    print(
        json.dumps(
            {
                "schema_version": migrated.get("schema_version"),
                "reviewed_count": migrated.get("reviewed_count"),
                "a_share_count": len(a_shares),
                "fingerprints_valid": fingerprints_valid,
                "missing_tickers": missing_tickers,
                "fingerprint_mismatches": fingerprint_mismatches,
                "written": not arguments.check,
            },
            ensure_ascii=False,
        )
    )
    return 1 if arguments.check and (missing_tickers or fingerprint_mismatches) else 0


if __name__ == "__main__":
    raise SystemExit(main())
