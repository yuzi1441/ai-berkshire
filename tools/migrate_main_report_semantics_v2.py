#!/usr/bin/env python3
"""Deterministically migrate candidate semantic contracts from v1 to v2.

The migration localizes existing ambiguity metadata.  It does not read market
facts, reinterpret reports, or invoke a model.  Re-running it is idempotent.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from main_report_semantic_schema import SEMANTIC_REVIEW_REASONS
from validate_main_report_semantics import CONTRACT_DIR, ROOT


ENTRY_BOUNDARY_CODES = {
    "ENTRY_ACTION_BOUNDARY", "VALUATION_ACTION_BOUNDARY",
    "CONSERVATIVE_ACTION_BOUNDARY", "POLICY_OR_PRICE_REVIEW_BOUNDARY",
    "ENTRY_PRICE_AND_FILING_SCOPE", "PRICE_BAND_ENTRY_STATUS_UNCLEAR",
    "REVIEW_NOT_BUY_SEMANTICS", "REVIEW_NOT_ENTRY",
    "AT_LEAST_TWO_OF_THREE_RELATION_UNCLEAR", "CURRENT_ZONE_ACTION_UNRESOLVED",
    "CURRENT_ACTION_TIMING", "CONFLICTING_ACTION_PRICE_BANDS",
    "REVIEW_ZONE_ACTION_BOUNDARY", "NO_EXPLICIT_ACTION_PRICE",
    "VALUATION_REVIEW_NOT_ENTRY", "GOVERNANCE_AND_SIGNAL_SCOPE",
}
HOLDER_CODES = {
    "MISSING_HOLDER_ACTION", "HOLDER_SCOPE_NOT_EXPLICIT", "HOLDER_COST_SCOPE",
    "SIGNAL_COMBINATION_UNSPECIFIED", "BUY_SIGNAL_COMBINATION_UNSPECIFIED",
    "REDUCE_EXIT_ACTION_UNSPECIFIED", "REDUCTION_TRIGGER_COMBINATION_UNSPECIFIED",
    "REDUCE_SIGNAL_COMBINATION_UNSPECIFIED",
}
MONITORING_CODES = {
    "CURRENT_PRICE_TIME_SENSITIVITY", "UNREPORTED_H1_DATA",
    "CYCLE_PEAK_UNCERTAINTY", "INVALIDATION_LOGIC_REQUIRES_REVIEW",
}
PRICE_ROLE_CODES = ENTRY_BOUNDARY_CODES | {
    "PRICE_AND_FUNDAMENTAL_PRECONDITION", "CONDITIONAL_PRICE_AND_FACTS",
    "PRICE_AND_CAPITAL_ALLOCATION_PRECONDITION",
}
SEMANTIC_LEGACY_MARKERS = (
    "AMBIGUOUS", "COMBINATION", "CONFLICT", "INCOMPLETE", "MULTI_MARKET",
    "A_H", "H_SHARE", "MULTIPLE_PRICE", "ACTION_BOUNDARY", "PRICE_ROLE",
    "SCOPE", "COMPLEX", "AT_LEAST", "UNCONDITIONAL", "PRECONDITION",
    "REVIEW_NOT", "INVALIDATION_LOGIC", "CURRENT_ACTION", "CURRENT_ZONE",
    "NO_EXPLICIT_ACTION", "CONDITIONAL_PRICE", "SIGNAL_SCOPE",
)


def _flatten(node: Any) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    return [node] + [item for child in node.get("children", []) for item in _flatten(child)]


def _all_conditions(contract: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for scope in contract.get("scopes", {}).values():
        for path in scope.get("action_paths", []):
            nodes.extend(_flatten(path.get("condition")))
    for field in ("hard_blocks", "redlines", "monitoring_conditions"):
        for node in contract.get(field, []):
            nodes.extend(_flatten(node))
    return nodes


def _path_ids(scope: dict[str, Any], *, unresolved_only: bool = False) -> list[str]:
    paths = scope.get("action_paths", [])
    if unresolved_only:
        paths = [
            path for path in paths
            if path.get("action") in {"REVIEW", "UNKNOWN", "ADD_POSITION", "REDUCE", "EXIT"}
            or "review" in str(path.get("path_id", "")).casefold()
            or "manual" in str(path.get("path_id", "")).casefold()
        ]
    return [str(path["path_id"]) for path in paths if path.get("path_id")]


def classify_ambiguity(contract: dict[str, Any], ambiguity: dict[str, Any]) -> dict[str, Any]:
    """Attach conservative scope/path metadata to an existing v1 ambiguity."""
    code = str(ambiguity.get("code", ""))
    empty = contract["scopes"]["empty_position"]
    holder = contract["scopes"]["holder"]
    entry_is_ambiguous = empty.get("entry_semantic") == "AMBIGUOUS"

    if entry_is_ambiguous:
        classification = "ENTRY"
        scopes = ["empty_position"]
        paths = _path_ids(empty)
        affects_entry = True
    elif code in HOLDER_CODES:
        classification = "EXIT_REDUCE" if any(
            marker in code for marker in ("REDUCE", "SIGNAL_COMBINATION")
        ) else "HOLDER"
        scopes = ["holder"]
        paths = _path_ids(holder, unresolved_only=True)
        affects_entry = False
    elif code in ENTRY_BOUNDARY_CODES:
        classification = "PATH_LOCAL"
        scopes = ["empty_position"]
        paths = _path_ids(empty, unresolved_only=True)
        # Some boundary reports encode the unresolved candidate as TRIAL rather
        # than REVIEW.  With no unresolved path selected, localize to all entry
        # paths instead of silently declaring the ambiguity harmless.
        if not paths:
            paths = [
                str(path["path_id"]) for path in empty.get("action_paths", [])
                if path.get("action") in {"OPEN_POSITION", "TRIAL_POSITION"}
            ]
        affects_entry = True
    elif code == "REPORT_CONTRACT_CONFLICT":
        classification = "GLOBAL"
        scopes = ["empty_position", "holder"]
        paths = []
        # Existing candidate paths remain usable, but the current/report-summary
        # disagreement remains visible to strong review.
        affects_entry = False
    elif code in MONITORING_CODES:
        classification = "MONITORING"
        scopes = ["empty_position"]
        paths = []
        affects_entry = False
    elif code == "REPORT_CONTRACT_INCOMPLETE":
        classification = "HOLDER" if holder.get("current_action") == "UNKNOWN" else "MONITORING"
        scopes = ["holder"] if classification == "HOLDER" else ["empty_position"]
        paths = _path_ids(holder, unresolved_only=True) if classification == "HOLDER" else []
        affects_entry = False
    elif code in {"MULTI_MARKET_REPORT_A_SHARE_SCOPE", "MULTI_MARKET_A_SHARE_SCOPE"}:
        classification = "GLOBAL"
        scopes = ["empty_position", "holder"]
        paths = []
        affects_entry = False
    else:
        # Unknown legacy codes remain fail-closed at the empty-position scope.
        classification = "GLOBAL"
        scopes = ["empty_position", "holder"]
        paths = []
        affects_entry = True

    migrated = copy.deepcopy(ambiguity)
    migrated.update({
        "classification": classification,
        "affected_scopes": scopes,
        "affected_path_ids": paths,
        "affects_entry": affects_entry,
    })
    return migrated


def semantic_review_reasons(contract: dict[str, Any]) -> list[str]:
    reasons: set[str] = set()
    scopes = contract.get("scopes", {})
    empty = scopes.get("empty_position", {})
    if empty.get("entry_semantic") == "UNCONDITIONAL_ENTRY_DEFINED":
        reasons.add("UNCONDITIONAL_ENTRY")
    if any(scope.get("semantic_status") != "ready" for scope in scopes.values()):
        reasons.add("SCOPE_AMBIGUITY")
    if any(path.get("semantic_status") == "ambiguous" for scope in scopes.values() for path in scope.get("action_paths", [])):
        reasons.add("PATH_LOCAL_AMBIGUITY")
    ambiguities = contract.get("ambiguities", [])
    if any(item.get("affects_entry") for item in ambiguities):
        reasons.add("ENTRY_AMBIGUOUS")
    if any(item.get("code") in PRICE_ROLE_CODES for item in ambiguities):
        reasons.add("PRICE_ROLE_AMBIGUITY")
    if any(item.get("classification") in {"HOLDER", "EXIT_REDUCE", "PATH_LOCAL"} for item in ambiguities):
        reasons.add("UNRESOLVED_ACTION_MEANING")
    if contract.get("report_contract_conflict", {}).get("present"):
        reasons.add("REPORT_CONTRACT_CONFLICT")

    nodes = _all_conditions(contract)
    if any(node.get("kind") == "ANY" for node in nodes):
        reasons.add("ANY_LOGIC")
    if any(node.get("kind") == "AT_LEAST" for node in nodes):
        reasons.add("AT_LEAST_N")
    if any(node.get("kind") == "NOT" for node in nodes):
        reasons.add("NOT_LOGIC")
    if any(
        node.get("children") and any(child.get("children") for child in node.get("children", []) if isinstance(child, dict))
        for node in nodes
    ):
        reasons.add("NESTED_LOGIC")

    instruments = {
        str(path.get("instrument_scope", "A_SHARE"))
        for scope in scopes.values() for path in scope.get("action_paths", [])
    } | {
        str(ref.get("instrument_scope", "A_SHARE"))
        for ref in contract.get("valuation_references", []) if isinstance(ref, dict)
    }
    if any(item not in {"A_SHARE", "UNKNOWN"} for item in instruments):
        reasons.add("MULTI_MARKET")
    ordered = [item for item in SEMANTIC_REVIEW_REASONS if item in reasons]
    return sorted(ordered, key=lambda item: (
        "UNCONDITIONAL_ENTRY SCOPE_AMBIGUITY PRICE_ROLE_AMBIGUITY NESTED_LOGIC ANY_LOGIC AT_LEAST_N REPORT_CONTRACT_CONFLICT MULTI_MARKET ENTRY_AMBIGUOUS CROSS_SCOPE_DEPENDENCY UNRESOLVED_ACTION_MEANING NOT_LOGIC PATH_LOCAL_AMBIGUITY".split().index(item)
    ))


def migrate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if contract.get("schema_version") == 2:
        return copy.deepcopy(contract)
    if contract.get("schema_version") != 1:
        raise ValueError(f"unsupported schema_version {contract.get('schema_version')!r}")

    migrated = copy.deepcopy(contract)
    migrated["schema_version"] = 2
    migrated["compiler"]["contract_version"] = "main-report-semantic-v2"
    migrated["ambiguities"] = [classify_ambiguity(migrated, item) for item in migrated.get("ambiguities", [])]

    for scope_name, scope in migrated["scopes"].items():
        scope["semantic_status"] = "ready"
        for path in scope.get("action_paths", []):
            path["semantic_status"] = "ready"

    for ambiguity in migrated["ambiguities"]:
        for scope_name in ambiguity["affected_scopes"]:
            scope = migrated["scopes"][scope_name]
            if ambiguity["classification"] == "ENTRY" or (
                scope_name == "holder" and scope.get("current_action") == "UNKNOWN"
            ):
                scope["semantic_status"] = "ambiguous"
            elif scope["semantic_status"] == "ready":
                scope["semantic_status"] = "partial"
        affected = set(ambiguity["affected_path_ids"])
        for scope in migrated["scopes"].values():
            for path in scope.get("action_paths", []):
                if path.get("path_id") in affected:
                    path["semantic_status"] = "ambiguous"

    migrated["semantic_status"] = "partial" if migrated["ambiguities"] else "ready"
    old_risks = [str(item) for item in migrated.pop("risk_reasons", [])]
    migrated["business_risk_reasons"] = sorted({
        item for item in old_risks
        if not any(marker in item.upper() for marker in SEMANTIC_LEGACY_MARKERS)
    })
    migrated["semantic_review_reasons"] = semantic_review_reasons(migrated)
    migrated["requires_strong_review"] = bool(migrated["semantic_review_reasons"])
    return migrated


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    paths = sorted((root / CONTRACT_DIR).glob("*.json"))
    migrated = [(path, migrate_contract(json.loads(path.read_text(encoding="utf-8")))) for path in paths]
    summary = {
        "contracts": len(migrated),
        "ready": sum(item[1]["semantic_status"] == "ready" for item in migrated),
        "partial": sum(item[1]["semantic_status"] == "partial" for item in migrated),
        "ambiguous": sum(item[1]["semantic_status"] == "ambiguous" for item in migrated),
        "entry_ambiguous": sum(
            item[1]["scopes"]["empty_position"]["semantic_status"] == "ambiguous"
            for item in migrated
        ),
        "strong_review": sum(item[1]["requires_strong_review"] for item in migrated),
    }
    if args.write:
        for path, payload in migrated:
            write_json(path, payload)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
