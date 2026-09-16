#!/usr/bin/env python3
"""Fail-closed validation for candidate canonical-report semantic contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import jsonschema

import current_reports
from main_report_semantic_schema import (
    ACTIONS,
    CONDITION_KINDS,
    EFFECTS,
    ENTRY_SEMANTICS,
    INSTRUMENT_SCOPES,
    PRICE_ROLES,
    SCOPES,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path("data/investment-dashboard")
CONTRACT_DIR = DATA_DIR / "main-report-semantic-contracts"
SCHEMA_PATH = Path(__file__).with_name("main_report_semantic_output_schema.json")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_REPORT_MARKERS = (
    "checklist",
    "thesis-drift",
    "thesis_drift",
    "technical",
    "技术分析",
    "论文追踪",
)
CHINESE_INTEGERS = {
    1: ("一", "壹"), 2: ("二", "两", "贰"), 3: ("三", "叁"),
    4: ("四", "肆"), 5: ("五", "伍"), 6: ("六", "陆"),
    7: ("七", "柒"), 8: ("八", "捌"), 9: ("九", "玖"),
    10: ("十", "拾"),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def a_share_tickers(repo_root: Path) -> set[str]:
    board = load_json(repo_root / DATA_DIR / "decision_board.json")
    decisions = board.get("decisions", []) if isinstance(board, dict) else []
    return {
        str(item.get("ticker"))
        for item in decisions
        if isinstance(item, dict) and item.get("market") == "A股" and item.get("ticker")
    }


def _walk_conditions(node: Any, location: str) -> Iterable[tuple[dict[str, Any], str]]:
    if not isinstance(node, dict):
        return
    yield node, location
    for index, child in enumerate(node.get("children", [])):
        yield from _walk_conditions(child, f"{location}.children[{index}]")


def _walk_contract_conditions(contract: dict[str, Any]) -> Iterable[tuple[dict[str, Any], str]]:
    for scope in ("empty_position", "holder"):
        scope_payload = contract.get("scopes", {}).get(scope, {})
        for index, path in enumerate(scope_payload.get("action_paths", [])):
            condition = path.get("condition") if isinstance(path, dict) else None
            if condition is not None:
                yield from _walk_conditions(
                    condition, f"scopes.{scope}.action_paths[{index}].condition"
                )
    for field in ("hard_blocks", "redlines", "monitoring_conditions"):
        for index, condition in enumerate(contract.get(field, [])):
                yield from _walk_conditions(condition, f"{field}[{index}]")


def _condition_requires_strong_review(node: Any) -> bool:
    """Return whether a condition shape is too easy to misread without a second reviewer."""
    if not isinstance(node, dict):
        return False
    kind = node.get("kind")
    children = node.get("children") if isinstance(node.get("children"), list) else []
    if kind in {"ANY", "AT_LEAST", "NOT"}:
        return True
    if kind == "ALL" and (
        len(children) > 2
        or any(_condition_requires_strong_review(child) for child in children)
    ):
        return True
    return any(_condition_requires_strong_review(child) for child in children)


def _contract_requires_strong_review(contract: dict[str, Any]) -> bool:
    """Fail closed on semantic outcomes that require a stronger review."""
    if contract.get("semantic_status") == "ambiguous":
        return True
    if any(
        isinstance(contract.get("scopes", {}).get(scope_name), dict)
        and contract["scopes"][scope_name].get("entry_semantic")
        == "UNCONDITIONAL_ENTRY_DEFINED"
        for scope_name in ("empty_position", "holder")
    ):
        return True
    if contract.get("report_contract_conflict", {}).get("present"):
        return True
    if contract.get("risk_reasons"):
        return True
    for scope_name in ("empty_position", "holder"):
        scope = contract.get("scopes", {}).get(scope_name, {})
        for path in scope.get("action_paths", []):
            if path.get("instrument_scope", "A_SHARE") not in {"A_SHARE", "UNKNOWN"}:
                return True
            if _condition_requires_strong_review(path.get("condition")):
                return True
    for field in ("hard_blocks", "redlines", "monitoring_conditions"):
        if any(_condition_requires_strong_review(node) for node in contract.get(field, [])):
            return True
    return any(
        isinstance(reference, dict)
        and reference.get("instrument_scope", "A_SHARE") not in {"A_SHARE", "UNKNOWN"}
        for reference in contract.get("valuation_references", [])
    )


def _walk_evidence(value: Any, location: str = "contract") -> Iterable[tuple[dict[str, Any], str]]:
    if isinstance(value, dict):
        if set(("report_path", "line_start", "line_end", "quote")).issubset(value):
            yield value, location
        for key, child in value.items():
            yield from _walk_evidence(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_evidence(child, f"{location}[{index}]")


def _number_tokens(value: int | float) -> set[str]:
    if isinstance(value, bool) or not math.isfinite(float(value)):
        return set()
    number = float(value)
    if number.is_integer():
        canonical = str(int(number))
    else:
        canonical = format(number, ".15g")
    tokens = {canonical, canonical.replace("-0.", "-.").replace("0.", ".")}
    integer = int(number) if number.is_integer() else None
    if integer in CHINESE_INTEGERS:
        tokens.update(CHINESE_INTEGERS[integer])
    if 0 < abs(number) < 1:
        percent = number * 100
        rendered = str(int(percent)) if percent.is_integer() else format(percent, ".15g")
        tokens.update({f"{rendered}%", f"{rendered}％"})
    return {token for token in tokens if token}


def _evidence_text(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    return "\n".join(
        str(item.get("quote", "")) for item in items if isinstance(item, dict)
    )


def _check_numeric_traceability(
    payload: dict[str, Any],
    location: str,
    numeric_fields: tuple[str, ...],
    errors: list[str],
) -> None:
    evidence_text = _evidence_text(payload.get("evidence"))
    for field in numeric_fields:
        value = payload.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if not any(token in evidence_text for token in _number_tokens(value)):
            errors.append(
                f"{location}.{field}: numeric value {value!r} is not traceable to local evidence"
            )


def _validate_condition(node: dict[str, Any], location: str, errors: list[str]) -> None:
    kind = node.get("kind")
    children = node.get("children") if isinstance(node.get("children"), list) else []
    if kind not in CONDITION_KINDS:
        errors.append(f"{location}.kind: unsupported condition kind {kind!r}")
        return
    if node.get("effect") not in EFFECTS:
        errors.append(f"{location}.effect: unsupported effect {node.get('effect')!r}")
    if node.get("scope") not in SCOPES:
        errors.append(f"{location}.scope: unsupported scope {node.get('scope')!r}")
    if kind in {"ALL", "ANY"} and len(children) < 2:
        errors.append(f"{location}: {kind} requires at least two children")
    elif kind == "AT_LEAST":
        minimum = node.get("minimum")
        if not isinstance(minimum, int) or isinstance(minimum, bool):
            errors.append(f"{location}: AT_LEAST requires integer minimum")
        elif minimum < 1 or minimum > len(children):
            errors.append(f"{location}: AT_LEAST minimum must be within child count")
    elif kind == "NOT" and len(children) != 1:
        errors.append(f"{location}: NOT requires exactly one child")
    elif kind not in {"ALL", "ANY", "AT_LEAST", "NOT"} and children:
        errors.append(f"{location}: leaf condition {kind} cannot contain children")
    if kind == "PRICE_RANGE":
        if node.get("price_min") is None and node.get("price_max") is None:
            errors.append(f"{location}: PRICE_RANGE requires price_min or price_max")
        if node.get("price_role") not in PRICE_ROLES:
            errors.append(f"{location}: PRICE_RANGE requires a valid price_role")
    elif node.get("price_role") not in (None, "UNKNOWN"):
        errors.append(f"{location}: non-price condition cannot declare actionable price_role")
    if kind == "METRIC_COMPARE" and not node.get("metric"):
        errors.append(f"{location}: METRIC_COMPARE requires metric")
    if kind in {"ALL", "ANY", "AT_LEAST", "NOT"}:
        _check_numeric_traceability(node, location, ("minimum",), errors)
    else:
        _check_numeric_traceability(
            node, location, ("value", "price_min", "price_max"), errors
        )


def validate_contract(
    contract: dict[str, Any],
    *,
    repo_root: Path = ROOT,
    expected_ticker: str | None = None,
    require_a_share: bool = True,
) -> list[str]:
    """Return every deterministic contract error; an empty list means valid."""
    errors: list[str] = []
    try:
        schema = load_json(repo_root / "tools/main_report_semantic_output_schema.json")
        jsonschema.Draft202012Validator(schema).validate(contract)
    except jsonschema.ValidationError as error:
        path = ".".join(str(item) for item in error.absolute_path) or "contract"
        errors.append(f"schema {path}: {error.message}")
        return errors
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as error:
        return [f"semantic schema unavailable: {error}"]

    ticker = contract.get("ticker")
    if expected_ticker is not None and ticker != expected_ticker:
        errors.append(f"ticker mismatch: expected {expected_ticker}, got {ticker}")
    if require_a_share and ticker not in a_share_tickers(repo_root):
        errors.append(f"ticker is not in the current A-share universe: {ticker}")

    registry_path = repo_root / DATA_DIR / current_reports.FILENAME
    try:
        registry = current_reports.load(registry_path, strict=True)
        canonical = registry["companies"].get(ticker)
    except (OSError, ValueError, TypeError, KeyError) as error:
        return errors + [f"canonical authority unavailable: {error}"]
    if not isinstance(canonical, dict):
        errors.append(f"ticker has no canonical current report: {ticker}")
        return errors

    source = contract.get("source", {})
    expected_path = canonical.get("current_main_report")
    expected_sha = canonical.get("content_sha256")
    if source.get("authority") != current_reports.FILENAME:
        errors.append("source.authority must be current_reports.json")
    if source.get("report_path") != expected_path:
        errors.append(
            f"source.report_path mismatch: expected {expected_path!r}, got {source.get('report_path')!r}"
        )
    if source.get("report_sha256") != expected_sha:
        errors.append("source.report_sha256 does not match current_reports.json")
    if not isinstance(expected_sha, str) or not HEX_64.fullmatch(expected_sha):
        errors.append(f"canonical SHA is malformed for {ticker}")
        return errors

    report = repo_root / str(expected_path)
    try:
        actual_sha = sha256(report)
        lines = report.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        errors.append(f"canonical report cannot be read: {error}")
        return errors
    if actual_sha != expected_sha:
        errors.append(f"canonical report SHA mismatch for {expected_path}")
    if contract.get("company") != canonical.get("company"):
        errors.append(
            f"company mismatch: expected {canonical.get('company')!r}, got {contract.get('company')!r}"
        )

    status = contract.get("semantic_status")
    ambiguities = contract.get("ambiguities", [])
    if status == "ready" and ambiguities:
        errors.append("ready contract cannot contain unresolved ambiguities")
    if status == "ambiguous" and not ambiguities:
        errors.append("ambiguous contract must explain at least one ambiguity")
    if status in {"ready", "ambiguous"} and contract.get("compiler", {}).get("pass") != 2:
        errors.append("final contract must come from adversarial pass 2")

    # High-risk semantic outcomes may remain valid candidates, but they must be
    # routed to stronger review before anyone can treat the interpretation as
    # finalized.
    if _contract_requires_strong_review(contract) and contract.get("requires_strong_review") is not True:
        errors.append(
            "high-risk semantic outcome requires requires_strong_review=true"
        )

    seen_evidence: set[tuple[Any, ...]] = set()
    for evidence, location in _walk_evidence(contract):
        key = (
            evidence.get("report_path"), evidence.get("line_start"),
            evidence.get("line_end"), evidence.get("quote"),
        )
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        if evidence.get("report_path") != expected_path:
            errors.append(f"{location}: evidence must reference only {expected_path}")
            continue
        lowered = str(evidence.get("report_path", "")).casefold()
        if any(marker.casefold() in lowered for marker in FORBIDDEN_REPORT_MARKERS):
            errors.append(f"{location}: forbidden non-main-report evidence path")
        start, end = evidence.get("line_start"), evidence.get("line_end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
            errors.append(f"{location}: invalid evidence line range")
            continue
        if end > len(lines):
            errors.append(f"{location}: evidence line range exceeds report length {len(lines)}")
            continue
        excerpt = "\n".join(lines[start - 1:end])
        if evidence.get("quote") not in excerpt:
            errors.append(f"{location}: quote is not present in the declared exact line range")

    if not seen_evidence:
        errors.append("contract contains no report evidence")

    node_ids: set[str] = set()
    for node, location in _walk_contract_conditions(contract):
        _validate_condition(node, location, errors)
        node_id = node.get("node_id")
        if node_id in node_ids:
            errors.append(f"{location}: duplicate condition node_id {node_id!r}")
        elif isinstance(node_id, str):
            node_ids.add(node_id)

    for scope_name in ("empty_position", "holder"):
        scope = contract.get("scopes", {}).get(scope_name, {})
        if scope.get("current_action") not in ACTIONS:
            errors.append(f"scopes.{scope_name}: invalid current_action")
        if scope.get("entry_semantic") not in ENTRY_SEMANTICS:
            errors.append(f"scopes.{scope_name}: invalid entry_semantic")
        path_ids: set[str] = set()
        for index, action_path in enumerate(scope.get("action_paths", [])):
            location = f"scopes.{scope_name}.action_paths[{index}]"
            if action_path.get("scope") not in {scope_name, "both"}:
                errors.append(f"{location}: action path leaks across position scopes")
            if action_path.get("instrument_scope", "A_SHARE") not in INSTRUMENT_SCOPES:
                errors.append(f"{location}: invalid instrument_scope")
            path_id = action_path.get("path_id")
            if path_id in path_ids:
                errors.append(f"{location}: duplicate path_id {path_id!r}")
            elif isinstance(path_id, str):
                path_ids.add(path_id)
            if not action_path.get("evidence"):
                errors.append(f"{location}: action path requires direct report evidence")
            price_nodes = [
                node for node in _flatten_condition(action_path.get("condition"))
                if node.get("kind") == "PRICE_RANGE"
            ]
            action = action_path.get("action")
            allowed_roles = {
                "OPEN_POSITION": {"UNCONDITIONAL_ENTRY", "CONDITIONAL_ENTRY"},
                "TRIAL_POSITION": {"TRIAL_ENTRY", "CONDITIONAL_ENTRY"},
                "ADD_POSITION": {"ADD_POSITION"},
                "REDUCE": {"REDUCE_POSITION"},
                "EXIT": {"EXIT_ZONE"},
                "REVIEW": {"REVIEW_ZONE", "WATCH_ZONE", "NOT_ACTIONABLE", "UNKNOWN"},
                "WATCH": {"WATCH_ZONE", "REVIEW_ZONE", "NOT_ACTIONABLE", "UNKNOWN"},
            }.get(action)
            if allowed_roles is not None:
                for node in price_nodes:
                    if node.get("price_role") not in allowed_roles:
                        errors.append(
                            f"{location}: {action} cannot use price role {node.get('price_role')}"
                        )
            if scope_name == "empty_position" and action == "ADD_POSITION":
                errors.append(f"{location}: holder add action cannot be an empty-position path")

        if not scope.get("evidence"):
            errors.append(f"scopes.{scope_name}: current scope stance requires evidence")

    if not contract.get("overall_stance", {}).get("evidence"):
        errors.append("overall_stance requires direct report evidence")
    for field, allowed_effects in (
        ("hard_blocks", {"BLOCK_ENTRY", "BLOCK_ADD"}),
        ("redlines", {"INVALIDATION", "NEGATIVE_TRIGGER", "REDUCE_TRIGGER", "EXIT_TRIGGER"}),
        ("monitoring_conditions", {"MONITOR", "REVIEW_ONLY"}),
    ):
        for index, node in enumerate(contract.get(field, [])):
            if node.get("effect") not in allowed_effects:
                errors.append(f"{field}[{index}]: effect {node.get('effect')} is incompatible")

    for index, reference in enumerate(contract.get("valuation_references", [])):
        _check_numeric_traceability(
            reference,
            f"valuation_references[{index}]",
            ("value", "min", "max"),
            errors,
        )
    return errors


def _flatten_condition(node: Any) -> list[dict[str, Any]]:
    if not isinstance(node, dict):
        return []
    result = [node]
    for child in node.get("children", []):
        result.extend(_flatten_condition(child))
    return result


def validate_file(path: Path, repo_root: Path = ROOT) -> list[str]:
    try:
        contract = load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot read contract {path}: {error}"]
    expected = path.stem if path.parent.name == CONTRACT_DIR.name else None
    return validate_contract(contract, repo_root=repo_root, expected_ticker=expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--all", action="store_true", help="validate every candidate contract")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    paths = [path if path.is_absolute() else root / path for path in args.paths]
    if args.all:
        paths.extend(sorted((root / CONTRACT_DIR).glob("*.json")))
    paths = list(dict.fromkeys(path.resolve() for path in paths))
    if not paths:
        parser.error("provide contract paths or --all")
    findings = {str(path.relative_to(root)): validate_file(path, root) for path in paths}
    if args.as_json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        for path, errors in findings.items():
            print(f"{path}: {'PASS' if not errors else 'FAIL'}")
            for error in errors:
                print(f"  - {error}")
    return 1 if any(findings.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
