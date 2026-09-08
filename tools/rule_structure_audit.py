#!/usr/bin/env python3
"""Audit Decision Rule structure without changing rule authority or evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = Path("data/investment-dashboard/decision_rules.json")
DEFAULT_EVALUATIONS = Path("data/investment-dashboard/rule_evaluations.json")
DEFAULT_OUTPUT = Path("logs/rule-structure-audit.json")

NON_EQUITY_PRICE_RE = re.compile(
    r"铜价|铝价|煤价|油价|锂价|碳酸锂|硅料价格|组件价格|产品(?:价格|单价)|"
    r"售价|均价|运价|电价|元\s*/\s*(?:吨|kW|瓦|平方米)|美元\s*/\s*吨",
    re.I,
)
EQUITY_PRICE_RE = re.compile(r"股价|股票价格|A股|H股|港股|每股|建仓价|买入价", re.I)
METRIC_RE = re.compile(
    r"毛利率|净利率|ROE|ROIC|自由现金流|FCF|收入|营收|利润|净现金|净债务|"
    r"现金流|市占率|销量|产能|资本开支|订单|回款|应收|存货|分红|成本|"
    r"铜价|铝价|煤价|油价|锂价|碳酸锂|单价|均价|售价",
    re.I,
)
VAGUE_EVENT_RE = re.compile(r"等待.*信号|条件满足|情况改善|出现机会|适当时机|继续观察", re.I)
COMPOSITE_RE = re.compile(r"且|并(?:且|扩大|保持|至少)?|同时|前提|后再|后可|以及|但|或.+或")

METRIC_NAMES = (
    "毛利率", "净利率", "ROE", "ROIC", "自由现金流", "FCF", "营收增速",
    "收入增速", "净利润增速", "净现金", "净债务", "铜价", "铝价", "煤价",
    "油价", "锂价", "碳酸锂价格", "产品单价", "产品价格", "均价", "售价",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("companies"), list):
        raise ValueError(f"invalid Decision Rule payload: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluation_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for company in (payload or {}).get("companies", []):
        if not isinstance(company, dict):
            continue
        for item in company.get("evaluations", []):
            if isinstance(item, dict) and item.get("rule_id"):
                result[str(item["rule_id"])] = item
    return result


def flatten_rules(
    payload: dict[str, Any], evaluations: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_rule = evaluation_map(evaluations)
    for company in payload.get("companies", []):
        if not isinstance(company, dict):
            continue
        for rule in company.get("rules", []):
            if isinstance(rule, dict):
                evaluation = by_rule.get(str(rule.get("rule_id") or ""), {})
                rows.append({
                    **rule,
                    "company": company.get("company"),
                    "ticker": company.get("ticker"),
                    "market": company.get("market"),
                    "status": evaluation.get("result", rule.get("status")),
                    "evaluation": evaluation or rule.get("evaluation") or {},
                })
    return rows


def is_non_equity_price(rule: dict[str, Any]) -> bool:
    if rule.get("type") not in {"PRICE", "PRICE_RANGE"}:
        return False
    condition = str(rule.get("condition") or "")
    return bool(NON_EQUITY_PRICE_RE.search(condition) and not EQUITY_PRICE_RE.search(condition))


def is_composite(rule: dict[str, Any]) -> bool:
    condition = str(rule.get("condition") or "")
    method = str(rule.get("extraction_method") or "")
    return "compound_condition" in method or bool(
        COMPOSITE_RE.search(condition)
        and (METRIC_RE.search(condition) or re.search(r"股价|价格|事件|政策|公告", condition))
    ) or bool(re.search(r"百分点.*(?:跌破|低于|高于)|毛利率.*净利润|净利润.*毛利率", condition))


def classify(rule: dict[str, Any]) -> tuple[str, bool, str]:
    """Return category, definition_structured, and an operator-facing reason."""
    rule_type = str(rule.get("type") or "")
    evaluation = rule.get("evaluation") if isinstance(rule.get("evaluation"), dict) else {}
    reason = str(evaluation.get("reason") or "")
    condition = str(rule.get("condition") or "")
    if is_non_equity_price(rule):
        return "non_equity_price_condition", False, "经营/商品价格被标成股票价格，不能使用证券行情求值"
    if rule_type == "METRIC" and evaluation.get("source_review_rule_id"):
        if reason in {"reviewed_evidence_insufficient", "awaiting_scheduled_evidence", "stale_human_review"}:
            return "true_missing_data", True, "定义已有人工锁定映射，但当前证据不足、未到期或已过期"
        return "other", True, "经营指标通过当前人工锁定定义和证据映射求值"
    if evaluation.get("source_review_rule_id"):
        if reason in {"reviewed_evidence_insufficient", "awaiting_scheduled_evidence", "stale_human_review"}:
            return "true_missing_data", True, "定义已有人工锁定映射，但当前证据不足、未到期或已过期"
        return "other", True, "当前 Rule 通过人工锁定定义和证据映射求值"
    if is_composite(rule):
        return "composite_condition", False, "同一 Rule 混合多个事实或逻辑连接词，需要拆成叶子条件和 ALL_OF/ANY_OF"
    if rule_type == "METRIC" and (
        rule.get("operator") is None or (rule.get("min") is None and rule.get("max") is None)
    ):
        return "metric_unstructured", False, "缺少 metric/operator/threshold/period/source 的可计算定义"
    if rule_type == "EVENT" and (VAGUE_EVENT_RE.search(condition) or METRIC_RE.search(condition)):
        return "event_unstructured", False, "事件描述过宽或混入经营指标，无法稳定绑定单一事件事实"
    if rule_type in {"PRICE", "PRICE_RANGE"} and (
        rule.get("operator") is None or (rule.get("min") is None and rule.get("max") is None)
    ):
        return "insufficient_definition", False, "价格 Rule 缺少有效 operator 或 boundary"
    if reason in {
        "quote_missing", "quote_missing_from_latest_refresh", "market_refresh_failed",
        "quote_date_missing", "historical_close_during_trading_session",
    } or str(rule.get("status") or "") == "data_error":
        return "provider_missing", True, "Rule 定义可求值，但当前数据源/行情快照不可用或不可信"
    if reason in {"awaiting_event_confirmation", "reviewed_evidence_insufficient", "awaiting_scheduled_evidence", "stale_human_review"}:
        return "true_missing_data", True, "Rule 定义存在，但当前缺少到期且可验证的事实证据"
    if rule_type not in {"PRICE", "PRICE_RANGE", "METRIC", "EVENT", "ALL_OF", "ANY_OF"}:
        return "insufficient_definition", False, "未知 Rule 类型"
    return "other", True, "当前定义可由既有 evaluator 或已审核证据处理"


def high_confidence_metric_proposal(rule: dict[str, Any]) -> dict[str, Any] | None:
    condition = re.sub(r"\s+", " ", str(rule.get("condition") or "")).strip()
    if is_composite(rule) or re.search(r"；|;|、", condition):
        return None
    names = [name for name in METRIC_NAMES if re.search(re.escape(name), condition, re.I)]
    if len(names) != 1:
        return None
    operator = None
    if re.search(r"不低于|至少|高于|超过|达到|≥|>=|>", condition):
        operator = "gte"
    elif re.search(r"不高于|不超过|低于|跌破|≤|<=|<", condition):
        operator = "lte"
    elif "转正" in condition:
        operator = "gt"
    if not operator:
        return None
    # Prefer values carrying an economic unit. This avoids interpreting the
    # "2" in "连续2个季度毛利率低于10%" as the threshold. Multiple distinct
    # unit-bearing values are ambiguous and remain manual.
    unit_values = re.findall(
        r"(?:\$\s*)?(-?\d[\d,]*(?:\.\d+)?)\s*(%|美元|元|港元|亿元|倍)",
        condition,
        re.I,
    )
    distinct_values = {(value.replace(",", ""), unit) for value, unit in unit_values}
    if len(distinct_values) > 1:
        return None
    number_value = next(iter(distinct_values), None)
    threshold = (
        0.0
        if "转正" in condition and number_value is None
        else float(number_value[0]) if number_value else None
    )
    if threshold is None:
        return None
    unit = number_value[1] if number_value else None
    period = None
    period_match = re.search(r"连续\s*(\d+|两|二)\s*(?:个)?(季度|报告期|半年度|年度)", condition)
    if period_match:
        count = 2 if period_match.group(1) in {"两", "二"} else int(period_match.group(1))
        period = {"count": count, "unit": period_match.group(2)}
    return {
        "type": "METRIC",
        "metric": names[0],
        "operator": operator,
        "threshold": threshold,
        "unit": unit,
        "period": period,
        "evidence_source": None,
        "confidence": "high",
        "apply_automatically": False,
        "proposal_only": True,
        "automatic_migration_candidate": False,
        "missing_authority_fields": [
            field
            for field, value in (
                ("period", period),
                ("authoritative_source", None),
            )
            if value is None
        ],
    }


def queue_item(rule: dict[str, Any], category: str, reason: str) -> dict[str, Any]:
    skills = {
        "non_equity_price_condition": ["financial-data"],
        "composite_condition": ["financial-data", "news-pulse"],
        "metric_unstructured": ["financial-data"],
        "event_unstructured": ["news-pulse"],
        "insufficient_definition": ["investment-research"],
    }.get(category, ["financial-data"])
    proposal = high_confidence_metric_proposal(rule) if category in {
        "non_equity_price_condition", "metric_unstructured"
    } else None
    return {
        "ticker": rule.get("ticker"),
        "company": rule.get("company"),
        "market": rule.get("market"),
        "rule_id": rule.get("rule_id"),
        "current_type": rule.get("type"),
        "condition": rule.get("condition"),
        "category": category,
        "why_not_automatic": reason,
        "recommended_skills": skills,
        "next_step": "补齐结构化定义并人工复核；在批准前保持 unknown，禁止猜测 met/not_met",
        "source_report": rule.get("source_report"),
        "source_line_start": rule.get("source_line_start"),
        "parseable_structure_proposal": proposal,
        "proposal_only": True,
        "automatic_migration_candidate": False,
        "missing_authority_fields": (
            proposal.get("missing_authority_fields")
            if proposal
            else ["structured_definition", "authoritative_source"]
        ),
    }


def data_backlog_item(rule: dict[str, Any], category: str, reason: str) -> dict[str, Any]:
    evaluation = rule.get("evaluation") if isinstance(rule.get("evaluation"), dict) else {}
    return {
        "ticker": rule.get("ticker"),
        "company": rule.get("company"),
        "market": rule.get("market"),
        "rule_id": rule.get("rule_id"),
        "current_type": rule.get("type"),
        "condition": rule.get("condition"),
        "category": category,
        "evaluation_status": rule.get("status"),
        "evaluation_reason": evaluation.get("reason"),
        "why_monitored": reason,
        "recommended_skills": ["financial-data"],
        "requires_user_action": False,
        "next_step": "后台等待或修复数据来源；不得因缺数猜测 met/not_met",
        "source_report": rule.get("source_report"),
        "source_line_start": rule.get("source_line_start"),
    }


def build_manifest(
    payload: dict[str, Any],
    source_path: Path,
    evaluations: dict[str, Any] | None = None,
    evaluations_path: Path | None = None,
) -> dict[str, Any]:
    rules = flatten_rules(payload, evaluations)
    audited = []
    definition_backlog = []
    data_backlog = []
    category_counts: Counter[str] = Counter()
    structured = 0
    for rule in rules:
        category, definition_structured, reason = classify(rule)
        category_counts[category] += 1
        structured += int(definition_structured)
        audited.append({
            "ticker": rule.get("ticker"),
            "company": rule.get("company"),
            "rule_id": rule.get("rule_id"),
            "type": rule.get("type"),
            "status": rule.get("status"),
            "evaluation_reason": (rule.get("evaluation") or {}).get("reason"),
            "definition_structured": definition_structured,
            "category": category,
        })
        if not definition_structured:
            definition_backlog.append(queue_item(rule, category, reason))
        elif category in {"provider_missing", "true_missing_data"}:
            data_backlog.append(data_backlog_item(rule, category, reason))
    candidates = sum(
        1 for item in definition_backlog if item.get("parseable_structure_proposal")
    )
    return {
        "schema_version": 1,
        "source": {
            "path": str(source_path),
            "sha256": sha256(source_path),
            "evaluations_path": str(evaluations_path) if evaluations_path else None,
            "evaluations_sha256": sha256(evaluations_path) if evaluations_path and evaluations_path.is_file() else None,
        },
        "summary": {
            "total_rules": len(rules),
            "structured_rules": structured,
            "unstructured_rules": len(rules) - structured,
            "category_counts": dict(sorted(category_counts.items())),
            "type_counts": dict(sorted(Counter(str(item.get("type")) for item in rules).items())),
            "status_counts": dict(sorted(Counter(str(item.get("status")) for item in rules).items())),
            "manual_rule_structuring_queue_count": len(definition_backlog),
            "definition_backlog_count": len(definition_backlog),
            "data_backlog_count": len(data_backlog),
            "parseable_structure_proposal_count": candidates,
            # A parsed threshold is not enough to migrate: a deterministic
            # period and authoritative evidence source are also required.
            "automatic_migration_candidate_count": 0,
        },
        "policy": {
            "fail_closed": True,
            "automatic_migration_performed": False,
            "audit_only": True,
            "consumed_by_decision_state": False,
            "note": "Parseable proposals are audit suggestions only; none has the full period/source contract required for automatic migration.",
        },
        "manual_rule_structuring_queue": sorted(
            definition_backlog,
            key=lambda item: (str(item.get("ticker")), str(item.get("rule_id"))),
        ),
        "data_backlog": sorted(
            data_backlog,
            key=lambda item: (str(item.get("ticker")), str(item.get("rule_id"))),
        ),
        "audit_items": sorted(audited, key=lambda item: (str(item.get("ticker")), str(item.get("rule_id")))),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--evaluations", type=Path, default=DEFAULT_EVALUATIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    source = args.rules if args.rules.is_absolute() else root / args.rules
    evaluations_path = args.evaluations if args.evaluations.is_absolute() else root / args.evaluations
    output = args.output if args.output.is_absolute() else root / args.output
    evaluations = load_json(evaluations_path) if evaluations_path.is_file() else None
    manifest = build_manifest(
        load_json(source), source, evaluations, evaluations_path if evaluations else None
    )
    write_json(output, manifest)
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
