#!/usr/bin/env python3
"""Build a local-only Candidate Shadow copy of the investment dashboard.

The output is deliberately isolated under ``.runtime`` by default.  It reuses
the semantic evaluator and persistent candidate stores, never mutates the
production decision board, and never promotes a candidate into Action Guidance.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import main_report_candidate_store as candidate_store
import main_report_current_facts as current_facts
import quote_quality
from validate_main_report_semantics import ROOT, load_json


SCHEMA_VERSION = 1
SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_OUTPUT = Path(".runtime/local-candidate-dashboard")
REQUIRED_REVIEW_STATUSES = {"PASS", "NEEDS_CLARIFICATION", "FAIL", "PENDING", "NOT_REQUIRED"}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _nodes(node: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children", []):
        yield from _nodes(child)


def _truth(node: dict[str, Any] | None, states: dict[str, str]) -> str:
    if not node:
        return "true"
    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    kind = node.get("kind")
    if not children:
        return states.get(str(node.get("node_id") or ""), "unknown")
    values = [_truth(child, states) for child in children]
    if kind == "ALL":
        return "false" if "false" in values else "unknown" if "unknown" in values else "true"
    if kind == "ANY":
        return "true" if "true" in values else "unknown" if "unknown" in values else "false"
    if kind == "AT_LEAST":
        minimum = int(node.get("minimum") or node.get("minimum_count") or 0)
        true_count, unknown_count = values.count("true"), values.count("unknown")
        return "true" if true_count >= minimum else "unknown" if true_count + unknown_count >= minimum else "false"
    if kind == "NOT":
        return {"true": "false", "false": "true"}.get(values[0], "unknown")
    return states.get(str(node.get("node_id") or ""), "unknown")


def _proof_leaf_ids(node: dict[str, Any] | None, states: dict[str, str]) -> list[str]:
    """Return one deterministic leaf proof for a currently true expression."""
    if not node:
        return []
    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    if not children:
        return [str(node.get("node_id"))] if _truth(node, states) == "true" else []
    kind = node.get("kind")
    if kind == "ALL":
        return [leaf for child in children for leaf in _proof_leaf_ids(child, states)]
    if kind == "ANY":
        selected = next((child for child in children if _truth(child, states) == "true"), None)
        return _proof_leaf_ids(selected, states)
    if kind == "AT_LEAST":
        minimum = int(node.get("minimum") or node.get("minimum_count") or 0)
        selected = [child for child in children if _truth(child, states) == "true"][:minimum]
        return [leaf for child in selected for leaf in _proof_leaf_ids(child, states)]
    if kind == "NOT":
        return [str(leaf.get("node_id")) for leaf in _nodes(node) if not leaf.get("children")]
    return []


def _unknown_dependencies(node: dict[str, Any] | None, states: dict[str, str]) -> tuple[set[str], set[str]]:
    """Return (individually mandatory, alternative) unknown leaf ids."""
    if not node:
        return set(), set()
    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    if not children:
        node_id = str(node.get("node_id") or "")
        return ({node_id}, set()) if states.get(node_id) == "unknown" else (set(), set())
    kind = node.get("kind")
    values = [_truth(child, states) for child in children]
    if kind == "ALL":
        if "false" in values:
            return set(), set()
        mandatory: set[str] = set()
        alternatives: set[str] = set()
        for child in children:
            child_required, child_alternatives = _unknown_dependencies(child, states)
            mandatory.update(child_required)
            alternatives.update(child_alternatives)
        return mandatory, alternatives
    if kind == "ANY":
        if "true" in values:
            alternatives = {
                str(leaf.get("node_id"))
                for child in children if _truth(child, states) == "unknown"
                for leaf in _nodes(child) if not leaf.get("children") and states.get(str(leaf.get("node_id"))) == "unknown"
            }
            return set(), alternatives
        unknowns = {
            str(leaf.get("node_id"))
            for child in children if _truth(child, states) == "unknown"
            for leaf in _nodes(child) if not leaf.get("children") and states.get(str(leaf.get("node_id"))) == "unknown"
        }
        return (unknowns, set()) if len([v for v in values if v == "unknown"]) == 1 else (set(), unknowns)
    if kind == "AT_LEAST":
        minimum = int(node.get("minimum") or node.get("minimum_count") or 0)
        needed = minimum - values.count("true")
        unknowns = {
            str(leaf.get("node_id"))
            for child in children if _truth(child, states) == "unknown"
            for leaf in _nodes(child) if not leaf.get("children") and states.get(str(leaf.get("node_id"))) == "unknown"
        }
        return (unknowns, set()) if needed == values.count("unknown") else (set(), unknowns)
    if kind == "NOT":
        return _unknown_dependencies(children[0], states)
    return set(), set()


def _semantic_review_status(row: dict[str, Any]) -> str:
    approval = row.get("semantic_review_approval")
    if approval in {"PASS", "FAIL", "NEEDS_CLARIFICATION"}:
        return str(approval)
    return "PENDING" if row.get("requires_strong_review") else "NOT_REQUIRED"


def candidate_record(
    row: dict[str, Any], contract: dict[str, Any], fact_packet: dict[str, Any], generated_at: str,
) -> dict[str, Any]:
    leaf_results = [item for item in fact_packet.get("leaf_results", []) if isinstance(item, dict)]
    states = {str(item.get("node_id")): str(item.get("current_state")) for item in leaf_results}
    leaves = {str(item.get("node_id")): item for item in leaf_results}
    paths = [
        path for path in contract.get("scopes", {}).get("empty_position", {}).get("action_paths", [])
        if path.get("instrument_scope", "A_SHARE") in {"A_SHARE", "BOTH"}
    ]
    matched = set(row.get("matched_path_ids", []))
    proof_ids: list[str] = []
    mandatory_unknown: set[str] = set()
    alternative_unknown: set[str] = set()
    alternative_path_unknowns: dict[str, list[str]] = {}
    for path in paths:
        path_id = str(path.get("path_id") or "")
        condition = path.get("condition")
        if path_id in matched:
            proof_ids.extend(_proof_leaf_ids(condition, states))
            _, alternatives = _unknown_dependencies(condition, states)
            alternative_unknown.update(alternatives)
        elif _truth(condition, states) == "unknown":
            required, alternatives = _unknown_dependencies(condition, states)
            ids = sorted(required | alternatives)
            alternative_path_unknowns[path_id] = ids
            if not matched:
                mandatory_unknown.update(required)
                alternative_unknown.update(alternatives)
    evidence_summary = []
    for node_id in dict.fromkeys(proof_ids):
        leaf = leaves.get(node_id, {})
        evidence_summary.append({
            "node_id": node_id,
            "description": leaf.get("description"),
            "state": leaf.get("current_state"),
            "resolution_method": leaf.get("resolution_method"),
            "evidence": (leaf.get("evidence") or [])[:2],
        })
    cutoffs = fact_packet.get("source_data_cutoff", {})
    price = fact_packet.get("price", {})
    return {
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "candidate_state": row.get("final_state"),
        "publication_status": row.get("publication_status"),
        "matched_path_ids": list(row.get("matched_path_ids", [])),
        "current_price": row.get("current_price"),
        "currency": "CNY",
        "mandatory_gate_count": len(dict.fromkeys(proof_ids)),
        "mandatory_gate_ids": list(dict.fromkeys(proof_ids)),
        "unknown_mandatory_gate_ids": sorted(mandatory_unknown),
        "alternative_unknown_gate_ids": sorted(alternative_unknown),
        "alternative_path_unknown_gate_ids": alternative_path_unknowns,
        "hard_block_state": row.get("hard_block_state"),
        "semantic_review_status": _semantic_review_status(row),
        "fact_cutoff": max((value for key, value in cutoffs.items() if key != "price" and value), default=None),
        "price_cutoff": cutoffs.get("price") or row.get("price_date"),
        "semantic_cutoff": cutoffs.get("semantic"),
        "evidence_summary": evidence_summary,
        "report_path": row.get("report_path"),
        "report_sha256": row.get("report_sha"),
        "semantic_contract_sha256": fact_packet.get("semantic_contract_sha256"),
        "generated_at": generated_at,
        "production_eligible": False,
        "shadow_mode": True,
    }


def validate_candidate_layer(payload: Any, expected_tickers: set[str] | None = None) -> list[str]:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return ["candidate layer schema_version must be 1"]
    errors: list[str] = []
    if payload.get("authority") != "candidate_shadow" or payload.get("production_consumable") is not False:
        errors.append("candidate layer must be non-production candidate_shadow")
    companies = payload.get("companies")
    if not isinstance(companies, list):
        return errors + ["candidate layer companies must be a list"]
    seen: set[str] = set()
    required = {
        "ticker", "company", "candidate_state", "publication_status", "matched_path_ids",
        "current_price", "currency", "mandatory_gate_count", "unknown_mandatory_gate_ids",
        "hard_block_state", "semantic_review_status", "fact_cutoff", "price_cutoff",
        "semantic_cutoff", "evidence_summary", "production_eligible",
    }
    for index, item in enumerate(companies):
        prefix = f"companies[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(required - item.keys())
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
        ticker = str(item.get("ticker") or "")
        if ticker in seen:
            errors.append(f"{prefix} duplicate ticker")
        seen.add(ticker)
        if not ticker.endswith((".SH", ".SZ", ".BJ")) or item.get("currency") != "CNY":
            errors.append(f"{prefix} is not an isolated A-share/CNY record")
        if item.get("production_eligible") is not False or item.get("shadow_mode") is not True:
            errors.append(f"{prefix} must remain shadow-only")
        if item.get("semantic_review_status") not in REQUIRED_REVIEW_STATUSES:
            errors.append(f"{prefix} semantic_review_status invalid")
    if expected_tickers is not None and seen != expected_tickers:
        errors.append(f"candidate ticker set mismatch: missing={sorted(expected_tickers-seen)}, extra={sorted(seen-expected_tickers)}")
    return errors


def _persistent_packets(repo_root: Path, evaluated_at: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_paths = sorted((repo_root / current_facts.CONTRACT_DIRECTORY).glob("*.json"))
    contracts = {path.stem: load_json(path) for path in contract_paths}
    paths = {path.stem: path for path in contract_paths}
    nodes = {ticker: current_facts.leaf_nodes(contract) for ticker, contract in contracts.items()}
    store = load_json(repo_root / current_facts.DEFAULT_PERSISTENT_RESOLUTIONS)
    errors = candidate_store.validate_resolution_store(store, contracts, paths, nodes, repo_root)
    if errors:
        raise ValueError("invalid persistent current facts: " + "; ".join(errors))
    packets, _ = candidate_store.reusable_fact_packets(store, contracts, paths, nodes, repo_root, evaluated_at.date())
    return {"schema_version": 1, "facts": packets}, contracts


def build_candidate_layer(
    repo_root: Path, quote_payload: dict[str, Any], evaluated_at: datetime, facts_directory: Path,
) -> dict[str, Any]:
    packets, contracts = _persistent_packets(repo_root, evaluated_at)
    reviews = load_json(repo_root / current_facts.DEFAULT_SEMANTIC_REVIEWS)
    preview = current_facts.build_preview(
        repo_root, quote_payload, packets, evaluated_at, reviews, facts_directory=facts_directory,
    )
    rows = {str(item.get("ticker")): item for item in preview["companies"]}
    companies = []
    for ticker in current_facts.PRIORITY_TICKERS:
        packet = load_json(facts_directory / f"{ticker}.json")
        companies.append(candidate_record(rows[ticker], contracts[ticker], packet, preview["generated_at"]))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "authority": "candidate_shadow",
        "production_consumable": False,
        "generated_at": preview["generated_at"],
        "price_cutoff": preview.get("price_cutoff"),
        "company_count": len(companies),
        "state_counts": dict(sorted(Counter(item["candidate_state"] for item in companies).items())),
        "companies": companies,
    }
    errors = validate_candidate_layer(payload, set(current_facts.PRIORITY_TICKERS))
    if errors:
        raise ValueError("invalid candidate layer: " + "; ".join(errors))
    return payload


def build_local_site(repo_root: Path, output_directory: Path, layer: dict[str, Any]) -> Path:
    source_site = repo_root / "site"
    site_output = output_directory / "site"
    if site_output.exists():
        shutil.rmtree(site_output)
    shutil.copytree(source_site, site_output)
    core_path = site_output / "data" / "dashboard_core.json"
    core = load_json(core_path)
    by_ticker = {item["ticker"]: item for item in layer["companies"]}
    rendered = 0
    for company in core.get("companyState", {}).get("companies", []):
        candidate = by_ticker.get(str(company.get("ticker") or ""))
        if candidate is None:
            continue
        if company.get("company") != candidate.get("company"):
            raise ValueError(f"dashboard company mismatch for {candidate['ticker']}")
        company["candidate_shadow"] = candidate
        rendered += 1
    if rendered != len(by_ticker):
        raise ValueError(f"candidate render population mismatch: {rendered}/{len(by_ticker)}")
    core["candidate_shadow"] = {
        "authority": "candidate_shadow", "production_consumable": False,
        "generated_at": layer["generated_at"], "company_count": rendered,
    }
    _write_json(core_path, core)
    _write_json(site_output / "data" / "candidate_decisions.json", layer)
    return site_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--quotes", type=Path)
    parser.add_argument("--refresh-prices", action="store_true")
    parser.add_argument("--as-of", help="ISO datetime in Asia/Shanghai")
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    output = (arguments.output_directory or repo_root / DEFAULT_OUTPUT).resolve()
    evaluated_at = datetime.fromisoformat(arguments.as_of) if arguments.as_of else datetime.now(SHANGHAI)
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=SHANGHAI)
    if arguments.refresh_prices:
        quotes = current_facts.refreshed_a_share_quotes(repo_root, evaluated_at)
        _write_json(output / "quote_input.json", quotes)
    else:
        quote_path = arguments.quotes or repo_root / current_facts.DEFAULT_QUOTES
        quote_path = quote_path if quote_path.is_absolute() else repo_root / quote_path
        quotes = load_json(quote_path)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="candidate-dashboard-facts-") as temporary:
        layer = build_candidate_layer(repo_root, quotes, evaluated_at, Path(temporary))
    _write_json(output / "candidate_decisions.json", layer)
    site_output = build_local_site(repo_root, output, layer)
    print(json.dumps({
        "status": "ok", "site": str(site_output), "candidate_artifact": str(output / "candidate_decisions.json"),
        "company_count": layer["company_count"], "state_counts": layer["state_counts"],
        "production_eligible_true": sum(item["production_eligible"] is True for item in layer["companies"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
