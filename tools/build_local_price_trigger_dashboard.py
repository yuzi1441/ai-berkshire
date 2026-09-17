#!/usr/bin/env python3
"""Build a local-only, price-only trigger layer and dashboard.

Price rules are compiled from semantic contracts only when ``--compile-rules``
is requested.  Ordinary quote refreshes consume that static rules artifact and
never load current-fact resolutions, review approvals, or the full semantic
evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import quote_quality


ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")
SCHEMA_VERSION = 1
CONTRACT_DIRECTORY = Path("data/investment-dashboard/main-report-semantic-contracts")
DEFAULT_QUOTES = Path("data/investment-dashboard/quotes/latest.json")
DEFAULT_OUTPUT = Path(".runtime/local-price-trigger-dashboard")
PRIORITY_TICKERS = (
    "002027.SZ", "600519.SH", "601127.SH", "603129.SH",
    "000400.SZ", "002028.SZ", "002352.SZ", "300274.SZ",
    "600309.SH", "601179.SH", "603288.SH", "688676.SH",
    "000568.SZ", "002415.SZ", "600276.SH", "600426.SH",
    "601126.SH", "603606.SH", "603659.SH", "605117.SH",
)
PRICE_STATES = {
    "NO_PRICE_PATH", "OUTSIDE_PRICE_ZONE", "PRICE_ZONE_MATCHED",
    "MULTIPLE_PRICE_ZONES_MATCHED", "PRICE_DATA_UNAVAILABLE",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _nodes(node: Any) -> Iterable[dict[str, Any]]:
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children", []):
        yield from _nodes(child)


def _non_price_leaves(node: Any) -> list[dict[str, Any]]:
    return [
        item for item in _nodes(node)
        if not item.get("children") and item.get("kind") != "PRICE_RANGE" and item.get("node_id")
    ]


def _manual_hints(node: Any, target_id: str) -> tuple[bool, list[dict[str, Any]]]:
    """Return non-price siblings and their structural relationship to a price leaf."""
    if not isinstance(node, dict):
        return False, []
    if str(node.get("node_id") or "") == target_id:
        return True, []
    children = [child for child in node.get("children", []) if isinstance(child, dict)]
    for selected in children:
        found, hints = _manual_hints(selected, target_id)
        if not found:
            continue
        relation = {
            "ALL": "REQUIRED_WITH_PRICE",
            "ANY": "ALTERNATIVE_TO_PRICE",
            "AT_LEAST": "CONTEXT_ONLY",
            "NOT": "CONTEXT_ONLY",
        }.get(str(node.get("kind")), "CONTEXT_ONLY")
        for sibling in children:
            if sibling is selected:
                continue
            for leaf in _non_price_leaves(sibling):
                hints.append({
                    "node_id": str(leaf.get("node_id")),
                    "kind": leaf.get("kind"),
                    "description": leaf.get("description"),
                    "relationship": relation,
                    "evidence": list(leaf.get("evidence") or []),
                })
        return True, hints
    return False, []


def _deduplicate_hints(hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for hint in hints:
        key = (str(hint.get("node_id")), str(hint.get("relationship")))
        if key not in seen:
            seen.add(key)
            result.append(hint)
    return result


def compile_price_rules(repo_root: Path, tickers: Iterable[str] = PRIORITY_TICKERS) -> dict[str, Any]:
    companies: list[dict[str, Any]] = []
    for ticker in tickers:
        contract_path = repo_root / CONTRACT_DIRECTORY / f"{ticker}.json"
        contract = load_json(contract_path)
        rules: list[dict[str, Any]] = []
        for scope_name, scope in contract.get("scopes", {}).items():
            for path in scope.get("action_paths", []):
                if path.get("instrument_scope", "A_SHARE") not in {"A_SHARE", "BOTH"}:
                    continue
                condition = path.get("condition")
                for node in _nodes(condition):
                    if node.get("kind") != "PRICE_RANGE" or node.get("currency") != "CNY":
                        continue
                    node_id = str(node.get("node_id") or "")
                    _, hints = _manual_hints(condition, node_id)
                    rules.append({
                        "rule_id": f"{path.get('path_id')}:{node_id}",
                        "path_id": path.get("path_id"),
                        "price_node_id": node_id,
                        "scope": path.get("scope") or scope_name,
                        "action": path.get("action"),
                        "price_role": node.get("price_role"),
                        "path_summary": path.get("summary"),
                        "price_description": node.get("description"),
                        "operator": node.get("operator"),
                        "price_min": node.get("price_min"),
                        "price_max": node.get("price_max"),
                        "currency": node.get("currency"),
                        "instrument_scope": path.get("instrument_scope", "A_SHARE"),
                        "path_semantic_status": path.get("semantic_status"),
                        "manual_check_conditions": _deduplicate_hints(hints),
                        "evidence": list(node.get("evidence") or path.get("evidence") or []),
                    })
        companies.append({
            "ticker": ticker,
            "company": contract.get("company"),
            "report_path": contract.get("report_path"),
            "report_sha256": contract.get("report_sha256"),
            "semantic_contract_sha256": _sha256(contract_path),
            "price_rules": rules,
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "authority": "semantic_contract_price_rules",
        "production_consumable": False,
        "company_count": len(companies),
        "rule_count": sum(len(item["price_rules"]) for item in companies),
        "companies": companies,
    }
    errors = validate_price_rules(payload, set(tickers))
    if errors:
        raise ValueError("invalid price trigger rules: " + "; ".join(errors))
    return payload


def validate_price_rules(payload: Any, expected_tickers: set[str] | None = None) -> list[str]:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return ["price rules schema_version must be 1"]
    errors: list[str] = []
    if payload.get("authority") != "semantic_contract_price_rules" or payload.get("production_consumable") is not False:
        errors.append("price rules must be local non-production semantic-contract output")
    seen: set[str] = set()
    rule_ids: set[str] = set()
    companies = payload.get("companies")
    if not isinstance(companies, list):
        return errors + ["price rules companies must be a list"]
    for company in companies:
        ticker = str(company.get("ticker") or "")
        seen.add(ticker)
        if not ticker.endswith((".SH", ".SZ", ".BJ")):
            errors.append(f"{ticker}: non-A-share ticker")
        for rule in company.get("price_rules", []):
            rule_id = str(rule.get("rule_id") or "")
            if not rule_id or rule_id in rule_ids:
                errors.append(f"{ticker}: missing or duplicate rule_id {rule_id}")
            rule_ids.add(rule_id)
            operator = rule.get("operator")
            if rule.get("currency") != "CNY" or operator not in {"BETWEEN", "LT", "LTE", "GT", "GTE"}:
                errors.append(f"{ticker}/{rule_id}: unsupported price rule")
            low, high = rule.get("price_min"), rule.get("price_max")
            valid_bounds = (
                operator == "BETWEEN" and isinstance(low, (int, float))
                and isinstance(high, (int, float)) and low <= high
            ) or (
                operator in {"LT", "LTE"} and isinstance(high, (int, float))
            ) or (
                operator in {"GT", "GTE"} and isinstance(low, (int, float))
            )
            if not valid_bounds:
                errors.append(f"{ticker}/{rule_id}: invalid price bounds")
    if expected_tickers is not None and seen != expected_tickers:
        errors.append(f"price-rule ticker set mismatch: missing={sorted(expected_tickers-seen)}, extra={sorted(seen-expected_tickers)}")
    return errors


def _eligible_quote(
    ticker: str, quote_payload: dict[str, Any], evaluated_at: datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    quote = quote_quality.with_quote_metadata(quote_payload).get(ticker)
    quality = quote_quality.quote_quality(quote, evaluated_at)
    return (quote if quality.get("eligible") else None), quality


def _price_matches(rule: dict[str, Any], price: float) -> bool:
    operator = rule.get("operator")
    if operator == "BETWEEN":
        return float(rule["price_min"]) <= price <= float(rule["price_max"])
    if operator == "LT":
        return price < float(rule["price_max"])
    if operator == "LTE":
        return price <= float(rule["price_max"])
    if operator == "GT":
        return price > float(rule["price_min"])
    if operator == "GTE":
        return price >= float(rule["price_min"])
    return False


def match_price_triggers(
    rules_payload: dict[str, Any], quote_payload: dict[str, Any], evaluated_at: datetime,
) -> dict[str, Any]:
    errors = validate_price_rules(rules_payload)
    if errors:
        raise ValueError("invalid price trigger rules: " + "; ".join(errors))
    companies: list[dict[str, Any]] = []
    for company in rules_payload["companies"]:
        ticker = str(company["ticker"])
        quote, quality = _eligible_quote(ticker, quote_payload, evaluated_at)
        price_rules = company.get("price_rules", [])
        matched = [] if quote is None else [
            rule for rule in price_rules
            if _price_matches(rule, float(quote["price"]))
        ]
        if not price_rules:
            state = "NO_PRICE_PATH"
        elif quote is None:
            state = "PRICE_DATA_UNAVAILABLE"
        elif len(matched) > 1:
            state = "MULTIPLE_PRICE_ZONES_MATCHED"
        elif matched:
            state = "PRICE_ZONE_MATCHED"
        else:
            state = "OUTSIDE_PRICE_ZONE"
        companies.append({
            "ticker": ticker,
            "company": company.get("company"),
            "price_state": state,
            "current_price": quote.get("price") if quote else None,
            "currency": quote.get("currency", "CNY") if quote else "CNY",
            "price_cutoff": quote.get("data_cutoff") if quote else quote_payload.get("data_cutoff"),
            "quote_quality": quality.get("reason"),
            "matched_rule_ids": [item["rule_id"] for item in matched],
            "matched_path_ids": list(dict.fromkeys(item["path_id"] for item in matched)),
            "matched_price_zones": matched,
            "available_price_zones": price_rules,
            "report_path": company.get("report_path"),
            "report_sha256": company.get("report_sha256"),
            "semantic_contract_sha256": company.get("semantic_contract_sha256"),
            "production_eligible": False,
            "shadow_mode": True,
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "authority": "price_trigger_shadow",
        "production_consumable": False,
        "generated_at": evaluated_at.isoformat(),
        "price_cutoff": quote_payload.get("data_cutoff"),
        "company_count": len(companies),
        "state_counts": dict(sorted(Counter(item["price_state"] for item in companies).items())),
        "companies": companies,
    }
    layer_errors = validate_price_trigger_layer(payload, {item["ticker"] for item in rules_payload["companies"]})
    if layer_errors:
        raise ValueError("invalid price trigger layer: " + "; ".join(layer_errors))
    return payload


def validate_price_trigger_layer(payload: Any, expected_tickers: set[str] | None = None) -> list[str]:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return ["price trigger layer schema_version must be 1"]
    errors: list[str] = []
    if payload.get("authority") != "price_trigger_shadow" or payload.get("production_consumable") is not False:
        errors.append("price trigger layer must remain shadow-only")
    seen: set[str] = set()
    for item in payload.get("companies", []):
        ticker = str(item.get("ticker") or "")
        seen.add(ticker)
        if item.get("price_state") not in PRICE_STATES:
            errors.append(f"{ticker}: invalid price state")
        if item.get("production_eligible") is not False or item.get("shadow_mode") is not True:
            errors.append(f"{ticker}: price trigger must not be production eligible")
        if item.get("currency") != "CNY" or not ticker.endswith((".SH", ".SZ", ".BJ")):
            errors.append(f"{ticker}: A-share/CNY isolation failed")
    if expected_tickers is not None and seen != expected_tickers:
        errors.append(f"price trigger ticker set mismatch: missing={sorted(expected_tickers-seen)}, extra={sorted(seen-expected_tickers)}")
    return errors


def build_local_site(repo_root: Path, output_directory: Path, layer: dict[str, Any]) -> Path:
    site_output = output_directory / "site"
    if site_output.exists():
        shutil.rmtree(site_output)
    shutil.copytree(repo_root / "site", site_output)
    core_path = site_output / "data" / "dashboard_core.json"
    core = load_json(core_path)
    by_ticker = {item["ticker"]: item for item in layer["companies"]}
    rendered = 0
    for company in core.get("companyState", {}).get("companies", []):
        trigger = by_ticker.get(str(company.get("ticker") or ""))
        if trigger is None:
            continue
        if company.get("company") != trigger.get("company"):
            raise ValueError(f"dashboard company mismatch for {trigger['ticker']}")
        company["price_trigger_shadow"] = trigger
        rendered += 1
    if rendered != len(by_ticker):
        raise ValueError(f"price trigger render population mismatch: {rendered}/{len(by_ticker)}")
    core["price_trigger_shadow"] = {
        "authority": "price_trigger_shadow", "production_consumable": False,
        "generated_at": layer["generated_at"], "company_count": rendered,
    }
    _write_json(core_path, core)
    _write_json(site_output / "data" / "price_triggers.json", layer)
    return site_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--rules", type=Path)
    parser.add_argument("--quotes", type=Path)
    parser.add_argument("--compile-rules", action="store_true")
    parser.add_argument("--as-of", help="ISO datetime in Asia/Shanghai")
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    output = (arguments.output_directory or repo_root / DEFAULT_OUTPUT).resolve()
    rules_path = (arguments.rules or output / "price_trigger_rules.json").resolve()
    quote_path = (arguments.quotes or repo_root / DEFAULT_QUOTES).resolve()
    evaluated_at = datetime.fromisoformat(arguments.as_of) if arguments.as_of else datetime.now(SHANGHAI)
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=SHANGHAI)
    if arguments.compile_rules:
        _write_json(rules_path, compile_price_rules(repo_root))
    if not rules_path.exists():
        parser.error("price rules artifact missing; run once with --compile-rules after contract changes")
    rules = load_json(rules_path)
    layer = match_price_triggers(rules, load_json(quote_path), evaluated_at)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "price_triggers.json", layer)
    site = build_local_site(repo_root, output, layer)
    print(json.dumps({
        "status": "ok", "site": str(site), "rules": str(rules_path),
        "price_trigger_artifact": str(output / "price_triggers.json"),
        "company_count": layer["company_count"], "state_counts": layer["state_counts"],
        "production_eligible_true": sum(item["production_eligible"] is True for item in layer["companies"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
