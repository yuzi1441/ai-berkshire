#!/usr/bin/env python3
"""Migrate the current dashboard decisions into structured state layers."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import decision_state  # noqa: E402
import decision_rule_extractor  # noqa: E402
import event_radar  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--board", type=Path, help="existing decision_board.json; defaults to the repository snapshot")
    parser.add_argument("--dry-run", action="store_true", help="show migration counts without writing any file")
    parser.add_argument("--write", action="store_true", help="write decision_rules, company_state and supporting snapshots")
    args = parser.parse_args()
    if not args.dry_run and not args.write:
        parser.error("choose --dry-run or --write")
    repo_root = args.repo_root.resolve()
    board_path = (args.board or repo_root / "data/investment-dashboard/decision_board.json").resolve()
    try:
        board = json.loads(board_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: cannot read board: {error}", file=sys.stderr)
        return 2
    decisions = [item for item in board.get("decisions", []) if isinstance(item, dict)]
    event_payload = event_radar.build_event_radar(repo_root, write=False)
    previous_rules = decision_state.load_json(
        repo_root / "data/investment-dashboard/decision_rules.json", {}
    )
    extracted_rules = decision_rule_extractor.build_payload(
        decisions,
        repo_root,
        previous_payload=previous_rules,
    )
    result = decision_state.build_state_layers(
        decisions,
        repo_root,
        event_payload=event_payload,
        rule_payload=extracted_rules,
        write=args.write,
        legacy_mode=True,
    )
    if args.write:
        decision_state.write_json(
            repo_root / decision_state.RULES_RELATIVE,
            decision_state.rule_definition_payload(result["rules"]),
        )
    errors = decision_state.validate_payloads(result)
    states = result["state"].get("companies", [])
    rules = result["rules"].get("companies", [])
    all_rules = [rule for company in rules for rule in company.get("rules", [])]
    rule_type_counts = Counter(rule.get("type", "UNKNOWN") for rule in all_rules)
    confidence_counts = Counter(rule.get("confidence", "unknown") for rule in all_rules)
    needs_review_examples = [
        {
            "ticker": company.get("ticker"),
            "company": company.get("company"),
            "rule_id": rule.get("rule_id"),
            "type": rule.get("type"),
            "condition": rule.get("condition"),
            "confidence": rule.get("confidence"),
            "source_section": rule.get("source_section"),
        }
        for company in rules
        for rule in company.get("rules", [])
        if rule.get("needs_review")
    ]
    summary = {
        "mode": "write" if args.write else "dry-run",
        "company_count": len(states),
        "rule_count": result["rules"].get("rule_count", 0),
        "rule_type_counts": dict(sorted(rule_type_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "high_confidence_rule_count": confidence_counts.get("high", 0),
        "needs_review_rule_count": len(needs_review_examples),
        "needs_review_company_count": len({item.get("ticker") for item in needs_review_examples}),
        "zero_rule_audit": extracted_rules.get("zero_rule_audit", {}),
        "needs_review_examples": needs_review_examples[:20],
        "lifecycle_counts": result["state"].get("summary", {}),
        "event_company_count": event_payload.get("company_count", 0),
        "validation_errors": errors,
        "outputs": [
            "data/investment-dashboard/decision_rules.json",
            "data/investment-dashboard/company_state.json",
            "data/investment-dashboard/technical_latest.json",
            "data/investment-dashboard/checklist_states.json",
        ] if args.write else [],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
