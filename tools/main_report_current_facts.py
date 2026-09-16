#!/usr/bin/env python3
"""Build a fail-closed candidate current-facts entry preview for A-share contracts.

This is intentionally not a production authority.  Semantic contracts define the
rules; node-bound fact packets only supply time-varying observations.  Composite
conditions and deterministic price nodes can never be overridden by packets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import evaluate_main_report_semantics as evaluator
import main_report_candidate_store as candidate_store
import market_snapshot
import quote_quality
from validate_main_report_semantics import ROOT, load_json, validate_contract


SCHEMA_VERSION = 1
SHANGHAI = ZoneInfo("Asia/Shanghai")
CONTRACT_DIRECTORY = Path("data/investment-dashboard/main-report-semantic-contracts")
DEFAULT_QUOTES = Path("data/investment-dashboard/quotes/latest.json")
DEFAULT_OUTPUT = Path(".runtime/main-report-current-facts/main_report_current_entry_preview.json")
DEFAULT_FACTS_OUTPUT = Path(".runtime/main-report-current-facts/facts")
DEFAULT_PILOT_LOG = Path("logs/main-report-current-facts-pilot.md")
DEFAULT_PRIORITY_LEAVES = Path(".runtime/main-report-current-facts/priority-unresolved-leaves.json")
DEFAULT_PRIORITY_AUDIT = Path(".runtime/main-report-current-facts/priority-resolution-audit.md")
DEFAULT_PERSISTENT_RESOLUTIONS = Path("data/investment-dashboard/main-report-current-fact-resolutions.json")
DEFAULT_SEMANTIC_REVIEWS = Path("data/investment-dashboard/main-report-semantic-review-approvals.json")
DEFAULT_PERSISTENT_AUDIT = Path(".runtime/main-report-current-facts/persistent-resolution-audit.md")
PILOT_TICKERS = (
    "603606.SH", "000333.SZ", "000568.SZ", "603129.SH", "000400.SZ",
    "000408.SZ", "002272.SZ", "600276.SH", "601727.SH", "002155.SZ",
)
PRIORITY_TICKERS = (
    "002027.SZ", "600519.SH", "601127.SH", "603129.SH",
    "000400.SZ", "002028.SZ", "002352.SZ", "300274.SZ",
    "600309.SH", "601179.SH", "603288.SH", "688676.SH",
    "000568.SZ", "002415.SZ", "600276.SH", "600426.SH",
    "601126.SH", "603606.SH", "603659.SH", "605117.SH",
)
SEMANTIC_LEAF_KINDS = evaluator.OVERRIDABLE_SEMANTIC_LEAF_KINDS
PACKET_KINDS = SEMANTIC_LEAF_KINDS | {"METRIC_COMPARE"}
PROHIBITED_SEMANTIC_SOURCES = {"technical", "sentiment", "opportunity"}
UNKNOWN_REASON_CODES = {
    "SOURCE_MISSING", "PERIOD_MISMATCH", "DISCLOSURE_NOT_FOUND",
    "QUALITATIVE_EVIDENCE_INSUFFICIENT", "METRIC_NOT_REPORTED",
    "TWO_SOURCE_MISMATCH", "EVENT_UNCONFIRMED", "FUTURE_DISCLOSURE",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _nodes(node: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children", []):
        yield from _nodes(child)


def evaluator_nodes(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return unique nodes the empty-position evaluator can consume."""
    result: dict[str, dict[str, Any]] = {}
    scope = contract.get("scopes", {}).get("empty_position", {})
    for path in scope.get("action_paths", []):
        if path.get("instrument_scope", "A_SHARE") not in {"A_SHARE", "BOTH"}:
            continue
        for node in _nodes(path.get("condition")):
            if node.get("node_id"):
                result[str(node["node_id"])] = node
    for node in contract.get("hard_blocks", []):
        if node.get("effect") != "BLOCK_ENTRY" or node.get("scope") not in {"empty_position", "both"}:
            continue
        for item in _nodes(node):
            if item.get("node_id"):
                result[str(item["node_id"])] = item
    return result


def leaf_nodes(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        node_id: node for node_id, node in evaluator_nodes(contract).items()
        if not node.get("children")
    }


def validate_fact_packets(
    packets: Any,
    contracts: dict[str, dict[str, Any]],
) -> list[str]:
    if not isinstance(packets, dict) or packets.get("schema_version") != SCHEMA_VERSION:
        return ["fact packets schema_version must be 1"]
    facts = packets.get("facts")
    if not isinstance(facts, list):
        return ["fact packets facts must be a list"]
    errors: list[str] = []
    identities: set[tuple[str, str]] = set()
    for index, fact in enumerate(facts):
        prefix = f"facts[{index}]"
        if not isinstance(fact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        ticker = str(fact.get("ticker") or "").upper()
        node_id = str(fact.get("node_id") or "")
        identity = (ticker, node_id)
        if identity in identities:
            errors.append(f"{prefix} duplicate ticker/node_id")
        identities.add(identity)
        contract = contracts.get(ticker)
        if contract is None:
            errors.append(f"{prefix} ticker is not an A-share semantic contract")
            continue
        node = evaluator_nodes(contract).get(node_id)
        if node is None:
            errors.append(f"{prefix} node_id is not bound to ticker")
            continue
        kind = str(fact.get("kind") or "")
        if str(fact.get("company") or "") != str(contract.get("company") or ""):
            errors.append(f"{prefix} company does not match contract")
        if kind != node.get("kind"):
            errors.append(f"{prefix} kind does not match contract node")
        if kind not in PACKET_KINDS or node.get("children"):
            errors.append(f"{prefix} composite/deterministic price override is forbidden")
        forbidden = {"operator", "threshold", "effect", "action"} & fact.keys()
        if forbidden:
            errors.append(f"{prefix} attempts to redefine semantic rule: {sorted(forbidden)}")
        evidence = fact.get("evidence")
        if isinstance(evidence, list):
            for evidence_index, item in enumerate(evidence):
                evidence_prefix = f"{prefix}.evidence[{evidence_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{evidence_prefix} must be an object")
                    continue
                for field in ("source_type", "source", "date", "value"):
                    if not str(item.get(field) or "").strip():
                        errors.append(f"{evidence_prefix}.{field} is required")
                if not str(item.get("source_path") or item.get("record") or "").strip():
                    errors.append(f"{evidence_prefix} requires source_path or record")
        if kind == "METRIC_COMPARE":
            explicit_unknown = "state" in fact and fact.get("state") in {None, "unknown"}
            if "state" in fact and not explicit_unknown:
                errors.append(f"{prefix}.state may only mark a metric fact unknown")
            if explicit_unknown:
                if fact.get("reason_code") not in UNKNOWN_REASON_CODES:
                    errors.append(f"{prefix}.reason_code is required for an unknown metric fact")
                continue
            value = fact.get("actual_value")
            try:
                if isinstance(value, bool) or not math.isfinite(float(value)):
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{prefix}.actual_value must be finite numeric")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{prefix}.evidence is required")
            elif len({str(item.get("source") or "") for item in evidence if isinstance(item, dict)}) < 2:
                errors.append(f"{prefix}.evidence requires two independent sources")
            if fact.get("unit") != node.get("unit"):
                errors.append(f"{prefix}.unit does not match contract node")
        else:
            state = fact.get("state")
            if state not in {True, False, None, "unknown"}:
                errors.append(f"{prefix}.state must be true, false, or unknown")
            if state in {True, False} and (not isinstance(evidence, list) or not evidence):
                errors.append(f"{prefix}.evidence is required for resolved semantic facts")
            source_types = {
                str(item.get("source_type") or "").lower()
                for item in evidence or [] if isinstance(item, dict)
            }
            if state in {True, False} and source_types & PROHIBITED_SEMANTIC_SOURCES:
                errors.append(f"{prefix} prohibited source cannot resolve a semantic condition")
            if state in {None, "unknown"} and fact.get("reason_code") not in UNKNOWN_REASON_CODES:
                errors.append(f"{prefix}.reason_code is required for an unknown semantic fact")
    return errors


def load_fact_packets(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "facts": []}
    return load_json(path)


def _fact_is_stale(fact: dict[str, Any], as_of: date) -> tuple[bool, str | None]:
    required = str(fact.get("required_period") or "")
    actual = str(fact.get("period") or "")
    if required and actual != required:
        return True, "reporting_period_mismatch"
    valid_until = str(fact.get("valid_until") or "")
    try:
        if valid_until and date.fromisoformat(valid_until) < as_of:
            return True, "fact_expired"
    except ValueError:
        return True, "invalid_valid_until"
    evidence_date = str(fact.get("evidence_date") or "")
    try:
        if evidence_date and date.fromisoformat(evidence_date) > as_of:
            return True, "future_evidence"
    except ValueError:
        return True, "invalid_evidence_date"
    return False, None


def _quote_result(
    ticker: str,
    quotes: dict[str, dict[str, Any]],
    evaluated_at: datetime,
) -> dict[str, Any]:
    quote = quotes.get(ticker)
    quality = quote_quality.quote_quality(quote, evaluated_at)
    if not isinstance(quote, dict):
        return {"state": "unknown", "reason": "quote_missing", "value": None}
    if quote.get("market") != "A股" or quote.get("currency") != "CNY":
        return {"state": "unknown", "reason": "instrument_or_currency_mismatch", "value": None}
    metadata = quote.get("_market_snapshot")
    if not isinstance(metadata, dict) or metadata.get("quote_type") != "close" or metadata.get("session") != "closed":
        return {"state": "unknown", "reason": "latest_complete_close_unavailable", "value": None,
                "date": quote.get("data_cutoff"), "source": quote.get("source")}
    if not quality.get("eligible"):
        return {
            "state": "unknown", "reason": quality.get("reason"), "value": None,
            "date": quote.get("data_cutoff"), "source": quote.get("source"), "quality": quality,
        }
    return {
        "state": "true", "reason": "current_complete_a_share_quote",
        "value": float(quote["price"]), "date": quote.get("data_cutoff"),
        "source": quote.get("source"), "provider_timestamp": quote.get("provider_timestamp"),
        "quality": quality,
    }


def _leaf_result(
    node: dict[str, Any],
    packet: dict[str, Any] | None,
    price: dict[str, Any],
    as_of: date,
) -> dict[str, Any]:
    kind = str(node.get("kind") or "")
    base = {
        "node_id": node.get("node_id"), "kind": kind,
        "description": node.get("description"), "effect": node.get("effect"),
    }
    if kind == "PRICE_RANGE":
        if price.get("state") != "true":
            return {**base, "current_state": "unknown", "resolution_method": "deterministic_price",
                    "reason": price.get("reason"), "evidence": [price]}
        state = evaluator.evaluate_condition(node, {"price": price["value"]})
        return {**base, "current_state": state, "resolution_method": "deterministic_price",
                "actual_value": price["value"], "evidence": [price]}
    if packet is None:
        return {**base, "current_state": "unknown", "resolution_method": "not_available",
                "reason": "node_bound_fact_missing", "evidence": []}
    if "state" in packet and packet.get("state") in {None, "unknown"}:
        return {**base, "current_state": "unknown", "resolution_method": "not_available",
                "reason": packet.get("reason_code"), "detail": packet.get("reason"),
                "evidence": packet.get("evidence", [])}
    stale, reason = _fact_is_stale(packet, as_of)
    if stale:
        return {**base, "current_state": "unknown", "resolution_method": "not_available",
                "reason": reason, "evidence": packet.get("evidence", []), "stale": True}
    if kind == "METRIC_COMPARE":
        state = evaluator.evaluate_condition(node, {"metrics": {node.get("metric"): packet["actual_value"]}})
        return {**base, "current_state": state, "resolution_method": "deterministic_metric",
                "actual_value": packet["actual_value"], "metric": node.get("metric"),
                "period": packet.get("period"), "evidence": packet.get("evidence", [])}
    value = packet.get("state")
    state = "true" if value is True else "false" if value is False else "unknown"
    return {**base, "current_state": state,
            "resolution_method": "semantic_review" if state != "unknown" else "not_available",
            "reason": packet.get("reason"), "evidence": packet.get("evidence", [])}


def _facts_for_evaluator(
    leaves: list[dict[str, Any]], price: dict[str, Any], contract_leaves: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    facts: dict[str, Any] = {"instrument_scope": "A_SHARE", "conditions": {}, "metrics": {}}
    if price.get("state") == "true":
        facts["price"] = price["value"]
    metric_values: dict[str, set[float]] = {}
    for result in leaves:
        node = contract_leaves[str(result["node_id"])]
        state = result.get("current_state")
        if node.get("kind") == "METRIC_COMPARE" and state != "unknown":
            metric_values.setdefault(str(node.get("metric")), set()).add(float(result["actual_value"]))
        elif node.get("kind") in SEMANTIC_LEAF_KINDS and state in {"true", "false"}:
            facts["conditions"][result["node_id"]] = state == "true"
    for metric, values in metric_values.items():
        if len(values) == 1:
            facts["metrics"][metric] = next(iter(values))
    return facts


def _source_cutoffs(leaves: list[dict[str, Any]], price: dict[str, Any]) -> dict[str, str | None]:
    buckets: dict[str, list[str]] = {
        "financial": [],
        "event_filing": [],
        "semantic": [],
    }
    for leaf in leaves:
        if leaf.get("current_state") == "unknown":
            continue
        kind = leaf.get("kind")
        if kind == "PRICE_RANGE":
            # A fresh quote must not make semantic evidence appear fresh.
            continue
        if kind == "METRIC_COMPARE":
            bucket = "financial"
        elif kind in {"EVENT", "FILING"}:
            bucket = "event_filing"
        else:
            bucket = "semantic"
        for evidence in leaf.get("evidence", []):
            if isinstance(evidence, dict) and evidence.get("date"):
                buckets[bucket].append(str(evidence["date"]))
    return {
        "price": price.get("date"),
        "financial": max(buckets["financial"], default=None),
        "event_filing": max(buckets["event_filing"], default=None),
        "semantic": max(buckets["semantic"], default=None),
    }


def _hard_block_state(result: dict[str, Any]) -> str:
    states = result.get("hard_blocks", [])
    if "true" in states:
        return "true"
    if "unknown" in states:
        return "unknown"
    if states and all(item == "false" for item in states):
        return "false"
    return "not_applicable"


def _publication_status(
    contract: dict[str, Any], evaluation: dict[str, Any], review_status: str | None = None,
) -> str:
    if evaluation.get("state") == "ENTRY_SEMANTIC_AMBIGUOUS":
        return "SEMANTIC_AMBIGUOUS"
    if evaluation.get("state") in {"PRICE_MATCHED_CONDITIONS_PENDING", "HARD_BLOCK_PENDING"}:
        return "FACTS_PENDING"
    if contract.get("requires_strong_review"):
        if review_status == "PASS":
            return "STRONG_REVIEW_PASSED"
        if review_status == "FAIL":
            return "SEMANTIC_REVIEW_FAILED"
        if review_status == "NEEDS_CLARIFICATION":
            return "SEMANTIC_AMBIGUOUS"
        return "STRONG_REVIEW_REQUIRED"
    return "CANDIDATE_READY"


def _persistent_audit_markdown(items: list[dict[str, Any]], generated_at: str) -> str:
    counts = Counter(str(item.get("effective_status")) for item in items)
    lines = [
        "# Persistent Current Fact Resolution Audit", "",
        f"> Evaluated at: {generated_at}",
        "> Candidate cache only; production_consumable=false.", "",
        f"- Records: {len(items)}",
        f"- VALID: {counts['VALID']}", f"- UNKNOWN: {counts['UNKNOWN']}",
        f"- STALE: {counts['STALE']}", f"- REVIEW_REQUIRED: {counts['REVIEW_REQUIRED']}", "",
    ]
    for item in items:
        lines.append(
            f"- `{item['ticker']}` / `{item['node_id']}`: "
            f"**{item['effective_status']}** ({item['reason']})"
        )
    return "\n".join(lines) + "\n"


def build_preview(
    repo_root: Path,
    quote_payload: dict[str, Any],
    packets: dict[str, Any],
    evaluated_at: datetime,
    review_store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract_paths = sorted((repo_root / CONTRACT_DIRECTORY).glob("*.json"))
    contracts = {path.stem: load_json(path) for path in contract_paths}
    contract_path_map = {path.stem: path for path in contract_paths}
    review_store = review_store or {
        "schema_version": 1, "authority": "candidate",
        "production_consumable": False, "approvals": [],
    }
    review_errors = candidate_store.validate_review_store(review_store, contracts, contract_path_map)
    if review_errors:
        raise ValueError("invalid semantic review approvals: " + "; ".join(review_errors))
    approvals = {str(item["ticker"]): item for item in review_store.get("approvals", [])}
    packet_errors = validate_fact_packets(packets, contracts)
    if packet_errors:
        raise ValueError("invalid current fact packets: " + "; ".join(packet_errors))
    packet_map = {
        (str(item["ticker"]).upper(), str(item["node_id"])): item
        for item in packets.get("facts", [])
    }
    quotes = quote_quality.with_quote_metadata(quote_payload)
    rows: list[dict[str, Any]] = []
    leaf_state_counts: Counter[str] = Counter()
    leaf_kind_counts: Counter[str] = Counter()
    unknown_reason_counts: Counter[str] = Counter()
    stale_count = 0
    facts_directory = repo_root / DEFAULT_FACTS_OUTPUT
    facts_directory.mkdir(parents=True, exist_ok=True)
    for path in contract_paths:
        ticker = path.stem
        contract = contracts[ticker]
        errors = validate_contract(contract, repo_root=repo_root, expected_ticker=ticker)
        if errors:
            rows.append({"ticker": ticker, "company": contract.get("company"),
                         "final_state": "NOT_EVALUATED", "errors": errors})
            continue
        price = _quote_result(ticker, quotes, evaluated_at)
        contract_leaves = leaf_nodes(contract)
        leaves = [
            _leaf_result(node, packet_map.get((ticker, node_id)), price, evaluated_at.date())
            for node_id, node in contract_leaves.items()
        ]
        for leaf in leaves:
            leaf_state_counts[str(leaf.get("current_state"))] += 1
            leaf_kind_counts[str(leaf.get("kind"))] += 1
            if leaf.get("current_state") == "unknown":
                unknown_reason_counts[str(leaf.get("reason") or "other")] += 1
            if leaf.get("stale"):
                stale_count += 1
        evaluation_facts = _facts_for_evaluator(leaves, price, contract_leaves)
        evaluation = evaluator.evaluate_contract(contract, evaluation_facts)
        counts = Counter(item["current_state"] for item in leaves)
        matched = [item["path_id"] for item in evaluation.get("paths", []) if item.get("truth") == "true"]
        unresolved = sorted(set(evaluation.get("unresolved_path_ids", [])) | {
            str(item["path_id"]) for item in evaluation.get("paths", []) if item.get("truth") == "unknown"
        })
        report = contract.get("source", {})
        review_status = candidate_store.approval_status(ticker, approvals, contract, path)
        packet = {
            "schema_version": SCHEMA_VERSION,
            "authority": "candidate_runtime_only",
            "ticker": ticker, "company": contract.get("company"),
            "instrument_scope": "A_SHARE", "as_of_date": evaluated_at.date().isoformat(),
            "source_data_cutoff": _source_cutoffs(leaves, price),
            "semantic_contract_version": contract.get("schema_version"),
            "semantic_contract_sha256": _sha256(path),
            "report_path": report.get("report_path"), "report_sha256": report.get("report_sha256"),
            "price": price, "leaf_results": leaves,
        }
        (facts_directory / f"{ticker}.json").write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        rows.append({
            "ticker": ticker, "company": contract.get("company"),
            "report_path": report.get("report_path"), "report_sha": report.get("report_sha256"),
            "semantic_contract_status": contract.get("semantic_status"),
            "empty_position_semantic_status": contract["scopes"]["empty_position"].get("semantic_status"),
            "requires_strong_review": bool(contract.get("requires_strong_review")),
            "semantic_review_reasons": contract.get("semantic_review_reasons", []),
            "current_price": price.get("value"), "price_date": price.get("date"),
            "price_status": price.get("state"), "final_state": evaluation["state"],
            "matched_path_ids": matched, "unresolved_path_ids": unresolved,
            "hard_block_state": _hard_block_state(evaluation),
            "semantic_review_approval": review_status,
            "publication_status": _publication_status(contract, evaluation, review_status),
            "conditions": {"true": counts["true"], "false": counts["false"], "unknown": counts["unknown"]},
            "reason_summary": _reason_summary(evaluation["state"], counts, price),
            "evaluated_paths": evaluation.get("paths", []),
        })
    state_counts = Counter(row["final_state"] for row in rows)
    return {
        "schema_version": SCHEMA_VERSION, "authority": "candidate_runtime_only",
        "production_consumable": False, "generated_at": evaluated_at.isoformat(timespec="seconds"),
        "instrument_scope": "A_SHARE", "company_count": len(rows),
        "price_cutoff": quote_payload.get("data_cutoff"),
        "current_facts_summary": {
            "leaf_states": dict(sorted(leaf_state_counts.items())),
            "leaf_kinds": dict(sorted(leaf_kind_counts.items())),
            "unknown_reasons": dict(sorted(unknown_reason_counts.items())),
            "stale": stale_count,
        },
        "state_counts": dict(sorted(state_counts.items())), "companies": rows,
    }


def _path_ids_by_node(contract: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    scope = contract.get("scopes", {}).get("empty_position", {})
    for path in scope.get("action_paths", []):
        if path.get("instrument_scope", "A_SHARE") not in {"A_SHARE", "BOTH"}:
            continue
        for node in _nodes(path.get("condition")):
            if node.get("node_id"):
                result.setdefault(str(node["node_id"]), []).append(str(path.get("path_id") or ""))
    for block in contract.get("hard_blocks", []):
        if block.get("effect") != "BLOCK_ENTRY" or block.get("scope") not in {"empty_position", "both"}:
            continue
        for node in _nodes(block):
            if node.get("node_id"):
                result.setdefault(str(node["node_id"]), []).append("HARD_BLOCK")
    return result


def _priority_path_audit(contract: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
    """Explain why each currently matched path remains actionable.

    Unknown leaves in an unused ANY branch are not mandatory gates.  A matched
    path has already evaluated true deterministically, so any unknown leaf it
    still contains is necessarily non-mandatory for that current evaluation.
    """
    evaluated = {
        str(item.get("path_id") or ""): item
        for item in row.get("evaluated_paths", []) if isinstance(item, dict)
    }
    scope = contract.get("scopes", {}).get("empty_position", {})
    result = []
    for path in scope.get("action_paths", []):
        path_id = str(path.get("path_id") or "")
        if path_id not in row.get("matched_path_ids", []):
            continue
        leaves = [node for node in _nodes(path.get("condition")) if not node.get("children")]
        non_price = [node for node in leaves if node.get("kind") != "PRICE_RANGE"]
        leaf_states = {
            str(item.get("node_id")): item.get("current_state")
            for item in row.get("leaf_results", []) if isinstance(item, dict)
        }
        unknown = [str(node.get("node_id")) for node in non_price
                   if leaf_states.get(str(node.get("node_id"))) == "unknown"]
        condition_state = evaluated.get(path_id, {}).get("truth")
        if path.get("condition") is None:
            path_type = "unconditional"
        elif not non_price:
            path_type = "pure_price"
        elif unknown and condition_state in {"true", True}:
            path_type = "alternate_branch_satisfied"
        else:
            path_type = "all_required_conditions_satisfied"
        result.append({
            "path_id": path_id, "action": path.get("action"),
            "instrument_scope": path.get("instrument_scope", "A_SHARE"),
            "semantic_status": path.get("semantic_status"),
            "condition_state": condition_state, "path_type": path_type,
            "non_price_leaf_ids": [str(node.get("node_id")) for node in non_price],
            "unknown_non_price_leaf_ids": unknown,
            "unknown_mandatory_gate_ids": [] if condition_state in {"true", True} else unknown,
        })
    return result


def _required_evidence(node: dict[str, Any]) -> str:
    kind = node.get("kind")
    if kind == "METRIC_COMPARE":
        return "同一报告期、单位和口径的结构化数值，并由两个独立可信来源交叉确认。"
    if kind == "FILING":
        return "指定正式披露已发布，且内容直接确认节点要求，而非只确认文件存在。"
    if kind == "EVENT":
        return "交易所、公司公告或其他正式材料对指定事件的明确确认。"
    if kind == "MANUAL_REVIEW":
        return "逐节点人工复核最新正式证据，并给出可追溯的 TRUE/FALSE/UNKNOWN 理由。"
    return "与节点原始语境直接对应的最新正式证据；部分支持不足以判定 TRUE。"


def build_priority_leaf_audit(repo_root: Path, preview: dict[str, Any]) -> dict[str, Any]:
    rows = {row["ticker"]: row for row in preview["companies"]}
    companies: list[dict[str, Any]] = []
    for ticker in PRIORITY_TICKERS:
        contract_path = repo_root / CONTRACT_DIRECTORY / f"{ticker}.json"
        facts_path = repo_root / DEFAULT_FACTS_OUTPUT / f"{ticker}.json"
        contract = load_json(contract_path)
        packet = load_json(facts_path)
        nodes = leaf_nodes(contract)
        path_ids = _path_ids_by_node(contract)
        leaves = []
        for result in packet["leaf_results"]:
            if result.get("kind") == "PRICE_RANGE":
                continue
            node_id = str(result["node_id"])
            node = nodes[node_id]
            leaves.append({
                "ticker": ticker, "company": contract.get("company"),
                "node_id": node_id, "kind": result.get("kind"),
                "effect": result.get("effect"), "description": result.get("description"),
                "path_ids": path_ids.get(node_id, []),
                "current_state": result.get("current_state"),
                "reason": result.get("reason"), "detail": result.get("detail"),
                "contract_evidence": node.get("evidence", []),
                "current_evidence": result.get("evidence", []),
                "required_reality_evidence": _required_evidence(node),
            })
        companies.append({
            "ticker": ticker, "company": contract.get("company"),
            "final_state": rows[ticker]["final_state"],
            "publication_status": rows[ticker]["publication_status"],
            "matched_path_audit": _priority_path_audit(
                contract, {**rows[ticker], "leaf_results": packet.get("leaf_results", [])}
            ),
            "leaves": leaves,
        })
    return {
        "schema_version": 1, "authority": "candidate_runtime_only",
        "generated_at": preview["generated_at"], "priority_count": len(companies),
        "companies": companies,
    }


def _priority_audit_markdown(
    preview: dict[str, Any], priority: dict[str, Any],
    baseline_preview: dict[str, Any] | None, baseline_priority: dict[str, Any] | None,
) -> str:
    current_rows = {row["ticker"]: row for row in preview["companies"]}
    before_rows = {
        row["ticker"]: row for row in (baseline_preview or {}).get("companies", [])
    }
    before_leaves = {
        (company["ticker"], leaf["node_id"]): leaf
        for company in (baseline_priority or {}).get("companies", [])
        for leaf in company.get("leaves", [])
    }
    lines = [
        "# Priority Current Facts Resolution Audit", "",
        f"> 生成时间：{preview['generated_at']}",
        "> Candidate runtime only；不属于 production authority。", "",
    ]
    for company in priority["companies"]:
        ticker = company["ticker"]
        row = current_rows[ticker]
        before = before_rows.get(ticker, {})
        lines.extend([
            f"## {row['company']}（{ticker}）", "",
            f"- Current price：{row.get('current_price')} CNY（{row.get('price_date')}）",
            f"- Final state before：`{before.get('final_state', row['final_state'])}`",
            f"- Final state after：`{row['final_state']}`",
            f"- Matched path：{', '.join(row.get('matched_path_ids', [])) or '无'}",
            f"- Hard block：`{row['hard_block_state']}`",
            f"- Strong review：`{str(row.get('requires_strong_review', False)).upper()}`",
            f"- Publication status：`{row['publication_status']}`", "",
            "### Matched path proof", "",
        ])
        if not company.get("matched_path_audit"):
            lines.append("- 当前没有匹配成功的行动路径。")
        for path in company.get("matched_path_audit", []):
            lines.append(
                f"- `{path['path_id']}` · action=`{path.get('action')}` · "
                f"type=`{path['path_type']}` · instrument=`{path['instrument_scope']}` · "
                f"condition=`{path.get('condition_state')}` · "
                f"non-price leaves={path['non_price_leaf_ids'] or '无'} · "
                f"unknown mandatory gates={path['unknown_mandatory_gate_ids'] or '无'}"
            )
        lines.extend([
            f"- Unresolved path warning：{', '.join(row.get('unresolved_path_ids', [])) or '无'}", "",
            "### Non-price entry leaves", "",
        ])
        if not company["leaves"]:
            lines.append("- 无非价格 evaluator leaf。")
        for leaf in company["leaves"]:
            old = before_leaves.get((ticker, leaf["node_id"]), {})
            evidence = "; ".join(
                str(item.get("source") or item.get("source_path") or "")
                for item in leaf.get("current_evidence", []) if isinstance(item, dict)
            )
            lines.append(
                f"- `{leaf['node_id']}` · {leaf['kind']} · before=`{old.get('current_state', leaf['current_state'])}` "
                f"→ after=`{leaf['current_state']}` · {leaf.get('description') or ''} · "
                f"reason={leaf.get('reason') or leaf.get('detail') or 'resolved'}"
                + (f" · evidence={evidence}" if evidence else "")
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def _reason_summary(state: str, counts: Counter, price: dict[str, Any]) -> str:
    if price.get("state") != "true":
        return f"价格不可用：{price.get('reason')}；求值保持失败关闭。"
    if state in {"BUY_READY", "TRIAL_READY"}:
        return "至少一条可用路径的全部条件成立；仍为候选预览，不是交易指令。"
    if state == "PRICE_MATCHED_CONDITIONS_PENDING":
        return f"价格已进入行动区，但仍有 {counts['unknown']} 个叶子事实未知。"
    if state == "PRICE_MATCHED_CONDITIONS_NOT_MET":
        return f"价格已进入行动区，但至少一个必要条件不成立。"
    if state == "ENTRY_SEMANTIC_AMBIGUOUS":
        return "合同的空仓进入语义仍有歧义，不能自动判断。"
    return f"确定性 evaluator 状态为 {state}；未知叶子 {counts['unknown']} 个。"


def _pilot_markdown(preview: dict[str, Any], facts_root: Path) -> str:
    by_ticker = {row["ticker"]: row for row in preview["companies"]}
    warning_count = sum(
        bool(by_ticker[ticker].get("requires_strong_review"))
        or by_ticker[ticker]["conditions"].get("unknown", 0) > 0
        for ticker in PILOT_TICKERS
    )
    lines = [
        "# Main Report Current Facts Pilot", "",
        f"> 生成时间：{preview['generated_at']}",
        "> 状态：candidate runtime audit；不属于 production authority。", "",
        f"- Pilot companies：{len(PILOT_TICKERS)}", f"- Structural PASS：{len(PILOT_TICKERS)}",
        f"- Fact/semantic WARNING：{warning_count}", "- FAIL：0", "",
    ]
    for ticker in PILOT_TICKERS:
        row = by_ticker[ticker]
        packet = load_json(facts_root / f"{ticker}.json")
        lines.extend([
            f"## {row['company']}（{ticker}）", "",
            f"- Main Report：`{row['report_path']}`", f"- Current Price：{row['current_price']} CNY（{row['price_date']}）",
            f"- Final Evaluator State：`{row['final_state']}`", f"- Hard Block：`{row['hard_block_state']}`",
            "- Structural Audit：`PASS`",
            f"- Strong Review：`{str(row.get('requires_strong_review', False)).upper()}`",
            f"- 条件统计：true={row['conditions']['true']} / false={row['conditions']['false']} / unknown={row['conditions']['unknown']}",
            f"- matched paths：{', '.join(row['matched_path_ids']) or '无'}",
            f"- unresolved paths：{', '.join(row['unresolved_path_ids']) or '无'}", "",
            "### Current leaf facts", "",
        ])
        for item in packet["leaf_results"]:
            evidence = "; ".join(
                str(evidence_item.get("source") or evidence_item.get("reason") or "")
                for evidence_item in item.get("evidence", []) if isinstance(evidence_item, dict)
            )
            lines.append(
                f"- `{item['node_id']}` · {item['kind']} · **{item['current_state']}** · "
                f"{item.get('description') or ''} · {item.get('reason') or item['resolution_method']}"
                + (f" · evidence: {evidence}" if evidence else "")
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def refreshed_a_share_quotes(repo_root: Path, evaluated_at: datetime) -> dict[str, Any]:
    board_path = repo_root / "data/investment-dashboard/decision_board.json"
    symbols = market_snapshot.load_watchlist(board_path, {"A股"})
    quotes = market_snapshot.fetch_quotes(symbols)
    stock_quotes = [dict(item, snapshot_status="current") for item in quotes if item.get("kind") != "index"]
    dates = sorted({str(item.get("data_cutoff")) for item in stock_quotes if item.get("data_cutoff")})
    quote_type = market_snapshot._market_quote_type("A股", evaluated_at, stock_quotes)
    session = market_snapshot._market_session("A股", evaluated_at)
    return {
        "schema_version": 1, "generated_at": evaluated_at.isoformat(timespec="seconds"),
        "source_status": "ok" if len(stock_quotes) == len(symbols) else "partial",
        "data_cutoff": dates[-1] if dates else None, "quotes": stock_quotes,
        "market_snapshots": {"A股": {
            "market": "A股", "quote_type": quote_type, "session": session,
            "source": "Tencent quote", "source_status": "ok" if len(stock_quotes) == len(symbols) else "partial",
            "refresh_status": "success" if stock_quotes else "failed",
            "data_cutoff": dates[-1] if dates else None,
            "last_attempted_at": evaluated_at.isoformat(timespec="seconds"),
            "last_success_at": evaluated_at.isoformat(timespec="seconds") if stock_quotes else None,
            "tracked_count": len(symbols), "quote_count": len(stock_quotes),
        }},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--quotes", type=Path)
    parser.add_argument("--fact-packets", type=Path)
    parser.add_argument("--persistent-resolutions", type=Path)
    parser.add_argument("--semantic-reviews", type=Path)
    parser.add_argument("--persistent-audit", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pilot-log", type=Path)
    parser.add_argument("--priority-leaves", type=Path)
    parser.add_argument("--priority-audit", type=Path)
    parser.add_argument("--as-of", help="ISO datetime; defaults to current Shanghai time")
    parser.add_argument("--refresh-prices", action="store_true", help="fetch A-share quotes in memory only")
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    evaluated_at = datetime.fromisoformat(arguments.as_of) if arguments.as_of else datetime.now(SHANGHAI)
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=SHANGHAI)
    if arguments.refresh_prices:
        quote_payload = refreshed_a_share_quotes(root, evaluated_at)
    else:
        quote_path = arguments.quotes or root / DEFAULT_QUOTES
        quote_path = quote_path if quote_path.is_absolute() else root / quote_path
        quote_payload = load_json(quote_path)
    fact_path = arguments.fact_packets
    if fact_path is not None and not fact_path.is_absolute():
        fact_path = root / fact_path
    packets = load_fact_packets(fact_path)
    explicit_packets = list(packets.get("facts", []))
    contract_paths = sorted((root / CONTRACT_DIRECTORY).glob("*.json"))
    contracts = {path.stem: load_json(path) for path in contract_paths}
    contract_path_map = {path.stem: path for path in contract_paths}
    nodes_by_ticker = {ticker: leaf_nodes(contract) for ticker, contract in contracts.items()}
    persistent_path = arguments.persistent_resolutions or root / DEFAULT_PERSISTENT_RESOLUTIONS
    persistent_path = persistent_path if persistent_path.is_absolute() else root / persistent_path
    persistent_audit: list[dict[str, Any]] = []
    if persistent_path.is_file():
        persistent = load_json(persistent_path)
        resolution_errors = candidate_store.validate_resolution_store(
            persistent, contracts, contract_path_map, nodes_by_ticker, root
        )
        if resolution_errors:
            raise ValueError("invalid persistent current facts: " + "; ".join(resolution_errors))
        cached_packets, persistent_audit = candidate_store.reusable_fact_packets(
            persistent, contracts, contract_path_map, nodes_by_ticker, root, evaluated_at.date()
        )
        # Fresh explicit runtime packets win over reusable candidate records.
        packet_map = {
            (str(item["ticker"]).upper(), str(item["node_id"])): item
            for item in cached_packets
        }
        packet_map.update({
            (str(item["ticker"]).upper(), str(item["node_id"])): item
            for item in explicit_packets
        })
        packets["facts"] = list(packet_map.values())
    review_path = arguments.semantic_reviews or root / DEFAULT_SEMANTIC_REVIEWS
    review_path = review_path if review_path.is_absolute() else root / review_path
    review_store = load_json(review_path) if review_path.is_file() else None
    output = arguments.output or root / DEFAULT_OUTPUT
    output = output if output.is_absolute() else root / output
    baseline_preview = load_json(output) if output.is_file() else None
    priority_output = arguments.priority_leaves or root / DEFAULT_PRIORITY_LEAVES
    priority_output = priority_output if priority_output.is_absolute() else root / priority_output
    baseline_priority = load_json(priority_output) if priority_output.is_file() else None
    preview = build_preview(root, quote_payload, packets, evaluated_at, review_store)
    preview["persistent_resolution_audit"] = persistent_audit
    persistent_audit_path = arguments.persistent_audit or root / DEFAULT_PERSISTENT_AUDIT
    persistent_audit_path = persistent_audit_path if persistent_audit_path.is_absolute() else root / persistent_audit_path
    persistent_audit_path.parent.mkdir(parents=True, exist_ok=True)
    persistent_audit_path.write_text(
        _persistent_audit_markdown(persistent_audit, evaluated_at.isoformat(timespec="seconds")),
        encoding="utf-8",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    priority = build_priority_leaf_audit(root, preview)
    priority_output.parent.mkdir(parents=True, exist_ok=True)
    priority_output.write_text(json.dumps(priority, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    priority_audit = arguments.priority_audit or root / DEFAULT_PRIORITY_AUDIT
    priority_audit = priority_audit if priority_audit.is_absolute() else root / priority_audit
    priority_audit.parent.mkdir(parents=True, exist_ok=True)
    priority_audit.write_text(
        _priority_audit_markdown(preview, priority, baseline_preview, baseline_priority),
        encoding="utf-8",
    )
    pilot_log = arguments.pilot_log or root / DEFAULT_PILOT_LOG
    pilot_log = pilot_log if pilot_log.is_absolute() else root / pilot_log
    pilot_log.parent.mkdir(parents=True, exist_ok=True)
    pilot_log.write_text(_pilot_markdown(preview, root / DEFAULT_FACTS_OUTPUT), encoding="utf-8")
    print(json.dumps({
        "status": "ok", "output": str(output), "pilot_log": str(pilot_log),
        "company_count": preview["company_count"], "price_cutoff": preview["price_cutoff"],
        "state_counts": preview["state_counts"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
