#!/usr/bin/env python3
"""Deterministically dry-evaluate a candidate main-report semantic contract."""

from __future__ import annotations

import argparse
import json
import operator
import sys
from pathlib import Path
from typing import Any

from main_report_semantic_schema import EVALUATION_STATES
from validate_main_report_semantics import ROOT, load_json, validate_contract

TRUE = "true"
FALSE = "false"
UNKNOWN = "unknown"


def _fact_override(node: dict[str, Any], facts: dict[str, Any]) -> Any:
    conditions = facts.get("conditions", {})
    return conditions.get(node.get("node_id")) if isinstance(conditions, dict) else None


def _truth(value: Any) -> str:
    if value is True:
        return TRUE
    if value is False:
        return FALSE
    return UNKNOWN


def evaluate_condition(node: dict[str, Any], facts: dict[str, Any]) -> str:
    override = _fact_override(node, facts)
    if override is not None:
        return _truth(override)
    kind = node.get("kind")
    children = node.get("children", [])
    states = [evaluate_condition(child, facts) for child in children]
    if kind == "ALL":
        return FALSE if FALSE in states else UNKNOWN if UNKNOWN in states else TRUE
    if kind == "ANY":
        return TRUE if TRUE in states else UNKNOWN if UNKNOWN in states else FALSE
    if kind == "AT_LEAST":
        minimum = int(node["minimum"])
        positives = states.count(TRUE)
        unknowns = states.count(UNKNOWN)
        if positives >= minimum:
            return TRUE
        if positives + unknowns < minimum:
            return FALSE
        return UNKNOWN
    if kind == "NOT":
        state = states[0]
        return FALSE if state == TRUE else TRUE if state == FALSE else UNKNOWN
    if kind == "PRICE_RANGE":
        price = facts.get("price")
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            return UNKNOWN
        low, high = node.get("price_min"), node.get("price_max")
        return _truth((low is None or price >= low) and (high is None or price <= high))
    if kind == "METRIC_COMPARE":
        metrics = facts.get("metrics", {})
        actual = metrics.get(node.get("metric")) if isinstance(metrics, dict) else None
        if actual is None:
            return UNKNOWN
        expected = node.get("value")
        operation = node.get("operator")
        operations = {
            "LT": operator.lt, "LTE": operator.le, "GT": operator.gt,
            "GTE": operator.ge, "EQ": operator.eq, "NE": operator.ne,
        }
        try:
            if operation in operations:
                return _truth(operations[operation](actual, expected))
            if operation == "EXISTS":
                return TRUE
        except TypeError:
            return UNKNOWN
        return UNKNOWN
    return UNKNOWN


def _leaf_states(node: dict[str, Any], facts: dict[str, Any]) -> list[tuple[str, str]]:
    children = node.get("children", [])
    if children:
        result: list[tuple[str, str]] = []
        for child in children:
            result.extend(_leaf_states(child, facts))
        return result
    return [(str(node.get("kind")), evaluate_condition(node, facts))]


def evaluate_contract(contract: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    """Evaluate empty-position entry paths without inventing unavailable facts."""
    status = contract.get("semantic_status")
    if status == "ambiguous":
        return {"state": "AMBIGUOUS", "paths": []}
    if status != "ready":
        return {"state": "NOT_EVALUATED", "paths": []}
    scope = contract["scopes"]["empty_position"]
    entry_semantic = scope.get("entry_semantic")
    if entry_semantic == "EXPLICIT_NO_BUY":
        return {"state": "EXPLICIT_NO_BUY", "paths": []}
    instrument_scope = str(facts.get("instrument_scope", "A_SHARE"))
    paths = [
        item for item in scope.get("action_paths", [])
        if item.get("action") in {"OPEN_POSITION", "TRIAL_POSITION"}
        and item.get("instrument_scope", "A_SHARE") in {instrument_scope, "BOTH"}
    ]
    if not paths:
        return {"state": "NO_ENTRY_PATH", "paths": []}

    block_states = [evaluate_condition(node, facts) for node in contract.get("hard_blocks", [])]
    if TRUE in block_states:
        return {"state": "BLOCKED", "paths": [], "hard_blocks": block_states}

    evaluated = []
    final_state = "NOT_EVALUATED"
    for path in paths:
        condition = path.get("condition")
        state = TRUE if condition is None else evaluate_condition(condition, facts)
        leaves = [] if condition is None else _leaf_states(condition, facts)
        price_states = [item[1] for item in leaves if item[0] == "PRICE_RANGE"]
        nonprice_states = [item[1] for item in leaves if item[0] != "PRICE_RANGE"]
        path_state = "NOT_EVALUATED"
        if state == TRUE and UNKNOWN not in block_states:
            path_state = "TRIAL_READY" if path.get("action") == "TRIAL_POSITION" else "BUY_READY"
        elif TRUE in price_states and (UNKNOWN in nonprice_states or UNKNOWN in block_states):
            path_state = "PRICE_MATCHED_CONDITIONS_PENDING"
        elif all(item == TRUE for item in nonprice_states) and UNKNOWN in price_states:
            path_state = "CONDITIONS_MET_PRICE_PENDING"
        elif any(item == TRUE for item in price_states) and state == FALSE:
            path_state = "BLOCKED"
        evaluated.append({"path_id": path.get("path_id"), "truth": state, "state": path_state})
        priority = [
            "BUY_READY", "TRIAL_READY", "PRICE_MATCHED_CONDITIONS_PENDING",
            "CONDITIONS_MET_PRICE_PENDING", "BLOCKED", "NOT_EVALUATED",
        ]
        if priority.index(path_state) < priority.index(final_state):
            final_state = path_state
    assert final_state in EVALUATION_STATES
    return {"state": final_state, "paths": evaluated, "hard_blocks": block_states}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--facts", type=Path, help="JSON facts file")
    parser.add_argument("--facts-json", help="inline JSON facts")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    path = args.contract if args.contract.is_absolute() else root / args.contract
    contract = load_json(path)
    errors = validate_contract(contract, repo_root=root, expected_ticker=path.stem)
    if errors:
        print(json.dumps({"state": "NOT_EVALUATED", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    if args.facts and args.facts_json:
        parser.error("use only one facts source")
    facts = load_json(args.facts) if args.facts else json.loads(args.facts_json or "{}")
    print(json.dumps(evaluate_contract(contract, facts), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
