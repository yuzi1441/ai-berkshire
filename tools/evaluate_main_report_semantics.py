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
OVERRIDABLE_SEMANTIC_LEAF_KINDS = {
    "QUALITATIVE", "EVENT", "FILING", "DATE", "MANUAL_REVIEW", "UNKNOWN",
}


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
    kind = node.get("kind")
    # Only semantic leaves that have no deterministic fact representation may
    # be supplied through facts.conditions.  Composite, price and metric nodes
    # are always computed below, so a caller cannot bypass the contract AST.
    if kind in OVERRIDABLE_SEMANTIC_LEAF_KINDS:
        override = _fact_override(node, facts)
        if override is not None:
            return _truth(override)
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


def _path_state(path: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    condition = path.get("condition")
    truth = TRUE if condition is None else evaluate_condition(condition, facts)
    leaves = [] if condition is None else _leaf_states(condition, facts)
    price_states = [state for kind, state in leaves if kind == "PRICE_RANGE"]
    nonprice_states = [state for kind, state in leaves if kind != "PRICE_RANGE"]
    action = path.get("action")

    state = "NOT_EVALUATED"
    if truth == TRUE:
        state = "TRIAL_READY" if action == "TRIAL_POSITION" else "BUY_READY"
    elif price_states:
        price_true = TRUE in price_states
        price_unknown = UNKNOWN in price_states
        nonprice_all_true = all(item == TRUE for item in nonprice_states)
        if price_true and truth == UNKNOWN:
            state = "PRICE_MATCHED_CONDITIONS_PENDING"
        elif price_true and truth == FALSE:
            state = "PRICE_MATCHED_CONDITIONS_NOT_MET"
        elif nonprice_all_true and price_unknown:
            state = "CONDITIONS_MET_PRICE_PENDING"
        elif nonprice_all_true and not price_unknown:
            state = "PRICE_NOT_REACHED"
    return {
        "path_id": path.get("path_id"),
        "truth": truth,
        "state": state,
        "price_states": price_states,
        "nonprice_states": nonprice_states,
    }


def _is_review_path(path: dict[str, Any]) -> bool:
    if path.get("action") not in {"REVIEW", "WATCH"}:
        return False
    condition = path.get("condition")
    return any(
        kind == "PRICE_RANGE"
        and node.get("price_role") in {"REVIEW_ZONE", "WATCH_ZONE"}
        for node in _condition_nodes(condition)
        for kind in [node.get("kind")]
    )


def _condition_nodes(node: Any) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    return [node] + [item for child in node.get("children", []) for item in _condition_nodes(child)]


def evaluate_contract(contract: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    """Evaluate empty-position entry paths without inventing unavailable facts."""
    if contract.get("schema_version") != 2:
        return {"state": "NOT_EVALUATED", "paths": [], "errors": ["schema v2 required"]}
    status = contract.get("semantic_status")
    if status not in {"ready", "partial"}:
        return {"state": "NOT_EVALUATED", "paths": []}
    scope = contract["scopes"]["empty_position"]
    entry_semantic = scope.get("entry_semantic")
    ambiguities = [
        item for item in contract.get("ambiguities", [])
        if "empty_position" in item.get("affected_scopes", []) and item.get("affects_entry")
    ]
    unresolved_path_ids = {
        str(path_id) for item in ambiguities for path_id in item.get("affected_path_ids", [])
    }
    global_entry_ambiguity = any(not item.get("affected_path_ids") for item in ambiguities)
    if (
        scope.get("semantic_status") == "ambiguous"
        or entry_semantic == "AMBIGUOUS"
        or global_entry_ambiguity
    ):
        return {
            "state": "ENTRY_SEMANTIC_AMBIGUOUS",
            "paths": [],
            "unresolved_path_ids": sorted(unresolved_path_ids),
            "warnings": [item.get("code") for item in ambiguities],
        }
    if entry_semantic == "EXPLICIT_NO_BUY":
        return {"state": "EXPLICIT_NO_BUY", "paths": []}
    instrument_scope = str(facts.get("instrument_scope", "A_SHARE"))
    all_paths = [
        item for item in scope.get("action_paths", [])
        if item.get("instrument_scope", "A_SHARE") in {instrument_scope, "BOTH"}
    ]
    paths = [
        item for item in all_paths
        if item.get("action") in {"OPEN_POSITION", "TRIAL_POSITION"}
        and item.get("semantic_status") == "ready"
    ]
    review_paths = [
        item for item in all_paths
        if item.get("semantic_status") == "ready" and _is_review_path(item)
    ]

    entry_blocks = [
        node for node in contract.get("hard_blocks", [])
        if node.get("effect") == "BLOCK_ENTRY"
        and node.get("scope") in {"empty_position", "both"}
    ]
    block_states = [evaluate_condition(node, facts) for node in entry_blocks]
    if TRUE in block_states:
        return {"state": "HARD_BLOCKED", "paths": [], "hard_blocks": block_states}

    evaluated = [_path_state(path, facts) for path in paths]
    review_evaluated = [
        {
            "path_id": path.get("path_id"),
            "truth": TRUE if path.get("condition") is None else evaluate_condition(path["condition"], facts),
            "state": "REVIEW_ZONE",
        }
        for path in review_paths
    ]
    review_matched = any(item["truth"] == TRUE for item in review_evaluated)

    priority = [
        "BUY_READY", "TRIAL_READY", "PRICE_MATCHED_CONDITIONS_PENDING",
        "PRICE_MATCHED_CONDITIONS_NOT_MET", "CONDITIONS_MET_PRICE_PENDING",
        "PRICE_NOT_REACHED", "NOT_EVALUATED",
    ]
    final_state = min(
        (item["state"] for item in evaluated),
        key=priority.index,
        default="NOT_EVALUATED",
    )
    if final_state in {"CONDITIONS_MET_PRICE_PENDING", "PRICE_NOT_REACHED", "NOT_EVALUATED"} and review_matched:
        final_state = "REVIEW_ZONE"
    if not paths and review_matched:
        final_state = "REVIEW_ZONE"
    elif not paths and not review_paths:
        final_state = "NO_ENTRY_PATH"
    elif not paths and not review_matched:
        final_state = "NO_ENTRY_PATH"

    if UNKNOWN in block_states and final_state in {"BUY_READY", "TRIAL_READY"}:
        final_state = "HARD_BLOCK_PENDING"
    assert final_state in EVALUATION_STATES
    return {
        "state": final_state,
        "paths": evaluated,
        "review_paths": review_evaluated,
        "hard_blocks": block_states,
        "unresolved_path_ids": sorted(unresolved_path_ids),
        "warnings": [item.get("code") for item in ambiguities],
    }


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
