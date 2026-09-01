#!/usr/bin/env python3
"""Small, auditable Decision Rules layer for the investment dashboard.

The module deliberately stays boring: rules are JSON records, evaluation is a
pure function, and qualitative rules fail closed to ``needs_review``.  It is a
bridge between a long-form main report and the existing lifecycle, Checklist,
and thesis-drift layers; it is not an order engine.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any, Callable


SCHEMA_VERSION = 1
RULE_CATEGORIES = {
    "entry",
    "improvement",
    "redline",
    "holding",
    "fundamental",
    "event",
    "composite",
}
TRIGGER_TYPES = {"price", "price_range", "metric", "event", "all_of", "any_of"}
AUTOMATION_LEVELS = {"auto", "review", "manual"}
RULE_STATUSES = {
    "inactive",
    "watching",
    "near_trigger",
    "triggered",
    "needs_review",
    "resolved",
    "disabled",
}
ACTION_KEYS = {
    "run_checklist",
    "thesis_review",
    "drift_warning",
    "review_add",
    "review_reduce",
    "review_exit",
    "keep_watch",
    "drop_review",
}

STATUS_LABELS = {
    "inactive": "未激活",
    "watching": "正常观察",
    "near_trigger": "接近触发",
    "triggered": "已触发",
    "needs_review": "待复核",
    "resolved": "已解决",
    "disabled": "已禁用",
}

DEFAULT_ACTION = "thesis_review"
DEFAULT_SOURCE = "main_report"
_MISSING = object()


def clean_text(value: Any, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or abs(number) == float("inf"):
        return None
    return number


def slug_company(value: Any) -> str:
    text = clean_text(value, 100).casefold()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text, flags=re.UNICODE).strip("-")
    return text or "unknown-company"


def company_id_for(item: dict[str, Any] | None) -> str:
    item = item if isinstance(item, dict) else {}
    return clean_text(item.get("company_id"), 100) or slug_company(item.get("company"))


def infer_currency(market: Any, ticker: Any = None) -> str | None:
    value = str(market or "")
    ticker_text = str(ticker or "").upper()
    if value == "A股" or ticker_text.endswith((".SH", ".SZ", ".BJ")):
        return "CNY"
    if value == "港股" or ticker_text.endswith(".HK"):
        return "HKD"
    if value == "美股":
        return "USD"
    return None


def _normal_operator(value: Any) -> str:
    operator = str(value or "").strip().lower()
    return {
        "＜": "<",
        "＞": ">",
        "≤": "<=",
        "≥": ">=",
        "等于": "==",
        "低于": "<",
        "以下": "<=",
        "不高于": "<=",
        "跌破": "<",
        "高于": ">",
        "超过": ">",
        "不低于": ">=",
        "达到": ">=",
    }.get(operator, operator)


def stable_rule_id(
    *,
    company_id: Any,
    ticker: Any,
    market: Any,
    trigger_type: Any,
    operator: Any,
    value: Any,
    source_report: Any,
    source_text: Any,
) -> str:
    seed = "|".join(
        clean_text(part, 500)
        for part in (
            company_id,
            str(ticker or "").upper(),
            market,
            trigger_type,
            operator,
            value,
            source_report,
            source_text,
        )
    )
    return f"rule_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def empty_layer() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": None,
        "description": "主报告与看板之间的增量决策规则层；规则触发只产生复核动作，不自动交易。",
        "rules": [],
        "migration": {},
    }


def normalize_rule(rule: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    """Normalize one JSON rule without inventing a missing threshold."""
    if not isinstance(rule, dict):
        raise ValueError("decision rule must be an object")
    trigger_type = str(rule.get("trigger_type") or "").strip().lower()
    if trigger_type not in TRIGGER_TYPES:
        raise ValueError(f"unsupported decision rule trigger_type: {trigger_type}")
    category = str(rule.get("category") or "fundamental").strip().lower()
    if category not in RULE_CATEGORIES:
        category = "fundamental"
    automation = str(rule.get("automation") or "review").strip().lower()
    if automation not in AUTOMATION_LEVELS:
        automation = "review"
    ticker = clean_text(rule.get("ticker"), 40).upper()
    market = clean_text(rule.get("market"), 20)
    currency = clean_text(rule.get("currency"), 10).upper()
    if not currency:
        currency = infer_currency(market, ticker) or ""
    company = clean_text(rule.get("company"), 120)
    company_id = clean_text(rule.get("company_id"), 120) or slug_company(company)
    source_report = clean_text(rule.get("source_report") or rule.get("source"), 500)
    source_text = clean_text(rule.get("source_text") or rule.get("description"), 360)
    created_at = clean_text(rule.get("created_at"), 40) or now or datetime.now().astimezone().isoformat(timespec="seconds")
    updated_at = clean_text(rule.get("updated_at"), 40) or created_at
    needs_review = rule.get("needs_review") is True
    enabled = rule.get("enabled") is not False
    status = str(rule.get("status") or "watching").strip().lower()
    if status not in RULE_STATUSES:
        status = "watching"
    if needs_review:
        status = "needs_review"
    elif not enabled:
        status = "disabled"
    value = rule.get("value", _MISSING)
    if trigger_type == "price_range":
        range_value = value if isinstance(value, dict) else {}
        value_min = rule.get("value_min", range_value.get("min"))
        value_max = rule.get("value_max", range_value.get("max"))
        min_number = finite_number(value_min)
        max_number = finite_number(value_max)
        if min_number is not None and max_number is not None and max_number < min_number:
            min_number, max_number = max_number, min_number
        normalized_value: Any = {
            "min": min_number if min_number is not None else value_min,
            "max": max_number if max_number is not None else value_max,
        }
    elif value is _MISSING:
        normalized_value = None
    else:
        normalized_value = value
    action = str(rule.get("action") or DEFAULT_ACTION).strip()
    action_key = str(rule.get("action_key") or "").strip().lower()
    if action_key not in ACTION_KEYS:
        action_key = action_key or _action_key_for(category, action)
    normalized = {
        "id": clean_text(rule.get("id"), 80)
        or stable_rule_id(
            company_id=company_id,
            ticker=ticker,
            market=market,
            trigger_type=trigger_type,
            operator=rule.get("operator"),
            value=normalized_value,
            source_report=source_report,
            source_text=source_text,
        ),
        "company_id": company_id,
        "company": company,
        "ticker": ticker,
        "market": market,
        "category": category,
        "trigger_type": trigger_type,
        "operator": _normal_operator(rule.get("operator")),
        "value": normalized_value,
        "currency": currency,
        "metric": clean_text(rule.get("metric"), 100),
        "event_type": clean_text(rule.get("event_type"), 100),
        "conditions": rule.get("conditions") if isinstance(rule.get("conditions"), list) else [],
        "action": action,
        "action_key": action_key,
        "description": clean_text(rule.get("description") or action, 240),
        "source": clean_text(rule.get("source") or DEFAULT_SOURCE, 80),
        "origin": clean_text(rule.get("origin"), 80),
        "source_report": source_report,
        "source_section": clean_text(rule.get("source_section"), 160),
        "source_text": source_text,
        "confidence": str(rule.get("confidence") or "medium").lower(),
        "automation": automation,
        "enabled": enabled,
        "needs_review": needs_review,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
    }
    if rule.get("current_value") is not None:
        normalized["current_value"] = rule.get("current_value")
    if rule.get("resolution_note"):
        normalized["resolution_note"] = clean_text(rule.get("resolution_note"), 240)
    return normalized


def _action_key_for(category: str, action: str) -> str:
    text = f"{category} {action}".lower()
    if "checklist" in text or "建仓" in text or "买入" in text:
        return "run_checklist"
    if "加仓" in text:
        return "review_add"
    if "减仓" in text:
        return "review_reduce"
    if "退出" in text or "卖出" in text:
        return "review_exit"
    if "观察" in text or "watch" in text:
        return "keep_watch"
    if "漂移" in text or "drift" in text:
        return "drift_warning"
    return "thesis_review"


def normalize_layer(payload: Any) -> dict[str, Any]:
    if payload is None:
        return empty_layer()
    if not isinstance(payload, dict):
        raise ValueError("decision rules layer must be a JSON object")
    version = payload.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported decision rules schema: {version}")
    raw_rules = payload.get("rules")
    if raw_rules is None:
        raw_rules = []
        for company_rules in (payload.get("companies") or {}).values():
            if isinstance(company_rules, dict):
                raw_rules.extend(company_rules.get("rules") or [])
    if not isinstance(raw_rules, list):
        raise ValueError("decision rules layer rules must be a list")
    rules = [normalize_rule(item) for item in raw_rules if isinstance(item, dict)]
    result = empty_layer()
    result.update({key: value for key, value in payload.items() if key not in {"rules", "companies"}})
    result["schema_version"] = SCHEMA_VERSION
    result["rules"] = rules
    return result


def rule_matches_decision(rule: dict[str, Any], decision: dict[str, Any]) -> bool:
    """Match market rules strictly; fundamental/event rules may use company_id."""
    rule_ticker = str(rule.get("ticker") or "").upper()
    ticker = str(decision.get("ticker") or "").upper()
    rule_market = str(rule.get("market") or "")
    market = str(decision.get("market") or "")
    is_price = rule.get("trigger_type") in {"price", "price_range"}
    if rule_ticker and rule_ticker != ticker:
        return False
    if rule_market and rule_market != market:
        return False
    if is_price and rule_ticker and rule_market and (rule_ticker != ticker or rule_market != market):
        return False
    if not is_price:
        rule_company_id = str(rule.get("company_id") or "")
        if rule_company_id and rule_company_id != company_id_for(decision):
            # A non-price rule with an explicit ticker can still be ticker-local.
            if not rule_ticker:
                return False
    rule_currency = str(rule.get("currency") or "").upper()
    decision_currency = str(decision.get("currency") or "").upper()
    if is_price and rule_currency and decision_currency and rule_currency != decision_currency:
        return False
    return True


def rules_for_decision(layer: dict[str, Any], decision: dict[str, Any]) -> list[dict[str, Any]]:
    payload = normalize_layer(layer)
    return [rule for rule in payload["rules"] if rule_matches_decision(rule, decision)]


def _context_value(context: dict[str, Any], rule: dict[str, Any]) -> Any:
    metric = str(rule.get("metric") or "").strip()
    metrics = context.get("metrics") if isinstance(context.get("metrics"), dict) else {}
    if metric in metrics:
        return metrics[metric]
    if rule.get("current_value") is not None:
        return rule.get("current_value")
    return None


def _compare(current: Any, operator: str, expected: Any) -> bool | None:
    actual = finite_number(current)
    target = finite_number(expected)
    if actual is None or target is None:
        return None
    return {
        "<": actual < target,
        "<=": actual <= target,
        ">": actual > target,
        ">=": actual >= target,
        "==": actual == target,
    }.get(_normal_operator(operator))


def _near(current: float, expected: float, threshold: float = 0.10) -> tuple[bool, float | None]:
    if expected == 0:
        return False, None
    distance = abs(current - expected) / abs(expected)
    return distance <= threshold, distance


def evaluate_rule(
    rule: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    resolver: Callable[[str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Evaluate a rule and return display-safe evidence, never an order."""
    normalized = normalize_rule(rule)
    context = context if isinstance(context, dict) else {}
    if not normalized["enabled"]:
        status = "needs_review" if normalized.get("needs_review") else "disabled"
        reason = "迁移候选待人工确认，未启用自动判断" if status == "needs_review" else "规则已禁用"
        return _evaluation(normalized, status, False, reason)
    if normalized["status"] == "resolved":
        return _evaluation(normalized, "resolved", True, normalized.get("resolution_note") or "规则已标记解决")
    trigger = normalized["trigger_type"]
    if trigger in {"all_of", "any_of"}:
        children: list[dict[str, Any]] = []
        for condition in normalized.get("conditions") or []:
            if isinstance(condition, dict):
                child = condition
                if condition.get("rule_id") and resolver:
                    child = resolver(str(condition["rule_id"])) or condition
                if not child.get("trigger_type"):
                    return _evaluation(normalized, "needs_review", False, "组合规则引用了未解析的子规则")
                children.append(child)
        if not children:
            return _evaluation(normalized, "needs_review", False, "组合规则缺少可评估条件")
        child_results = [evaluate_rule(child, context, resolver=resolver) for child in children]
        statuses = [item["status"] for item in child_results]
        triggered = sum(status == "triggered" for status in statuses)
        near = sum(status == "near_trigger" for status in statuses)
        review = sum(status == "needs_review" for status in statuses)
        if trigger == "all_of":
            if triggered == len(statuses):
                status = "triggered"
            elif review:
                status = "needs_review"
            elif triggered or near:
                status = "near_trigger"
            else:
                status = "watching"
        else:
            if triggered:
                status = "triggered"
            elif review and not near:
                status = "needs_review"
            elif near:
                status = "near_trigger"
            else:
                status = "watching"
        return _evaluation(
            normalized,
            status,
            status not in {"needs_review", "inactive", "disabled"},
            f"组合条件 {triggered}/{len(statuses)} 条已满足",
            children=child_results,
        )

    if normalized["automation"] != "auto":
        current = _context_value(context, normalized)
        if current is None and not context.get("events"):
            return _evaluation(normalized, "needs_review", False, "该规则需要财报/Agent/人工上下文，当前无法自动判断")

    if trigger == "price":
        current = context.get("price")
        expected = normalized.get("value")
        result = _compare(current, normalized.get("operator"), expected)
        if result is None:
            return _evaluation(normalized, "needs_review", False, "缺少同市场同币种当前价格，无法自动判断", current_value=current)
        target = finite_number(expected)
        distance = abs(float(current) - target) / abs(target) if target not in (None, 0) else None
        status = "triggered" if result else ("near_trigger" if distance is not None and distance <= 0.10 else "watching")
        return _evaluation(normalized, status, True, _price_reason(normalized, current), current_value=current, distance_pct=distance)

    if trigger == "price_range":
        value = normalized.get("value") if isinstance(normalized.get("value"), dict) else {}
        minimum = finite_number(value.get("min"))
        maximum = finite_number(value.get("max"))
        current = finite_number(context.get("price"))
        if minimum is None or maximum is None:
            return _evaluation(normalized, "needs_review", False, "价格区间缺少上下限，无法自动判断", current_value=current)
        if current is None:
            return _evaluation(normalized, "needs_review", False, "缺少同市场同币种当前价格，无法自动判断")
        if minimum <= current <= maximum:
            status = "triggered"
            distance = 0.0
        elif current < minimum:
            status = "triggered"
            distance = (minimum - current) / minimum if minimum else None
        else:
            close, distance = _near(current, maximum)
            status = "near_trigger" if close else "watching"
        return _evaluation(normalized, status, True, _range_reason(normalized, current), current_value=current, distance_pct=distance)

    if trigger == "metric":
        current = _context_value(context, normalized)
        result = _compare(current, normalized.get("operator"), normalized.get("value"))
        if result is None:
            return _evaluation(normalized, "needs_review", False, "缺少经确认的当前指标，无法自动判断", current_value=current)
        status = "triggered" if result else "watching"
        return _evaluation(normalized, status, normalized["automation"] == "auto", _metric_reason(normalized, current), current_value=current)

    if trigger == "event":
        events = context.get("events")
        if not isinstance(events, list):
            return _evaluation(normalized, "needs_review", False, "缺少事件核验结果，无法自动判断")
        event_type = str(normalized.get("event_type") or "").casefold()
        description = str(normalized.get("description") or "").casefold()
        matched = []
        for event in events:
            blob = clean_text(event.get("summary") if isinstance(event, dict) else event, 300).casefold()
            kind = clean_text(event.get("event_type") if isinstance(event, dict) else "", 100).casefold()
            if (event_type and (event_type in kind or event_type in blob)) or (description and description in blob):
                matched.append(event)
        status = "triggered" if matched else "watching"
        return _evaluation(normalized, status, True, "已匹配事件" if matched else "当前事件样本未匹配该规则", matched_events=matched)

    return _evaluation(normalized, "needs_review", False, "未知规则类型，无法自动判断")


def _evaluation(rule: dict[str, Any], status: str, auto_evaluable: bool, reason: str, **extra: Any) -> dict[str, Any]:
    result = {
        "rule_id": rule["id"],
        "status": status if status in RULE_STATUSES else "needs_review",
        "status_label": STATUS_LABELS.get(status, STATUS_LABELS["needs_review"]),
        "auto_evaluable": auto_evaluable,
        "reason": clean_text(reason, 300),
        "rule": rule,
    }
    result.update(extra)
    return result


def _price_reason(rule: dict[str, Any], current: Any) -> str:
    return f"当前价格 {current} {rule.get('currency') or ''} 满足规则 {rule.get('operator')} {rule.get('value')}"


def _range_reason(rule: dict[str, Any], current: Any) -> str:
    value = rule.get("value") or {}
    return f"当前价格 {current} {rule.get('currency') or ''} 对照区间 {value.get('min')}–{value.get('max')}"


def _metric_reason(rule: dict[str, Any], current: Any) -> str:
    return f"{rule.get('metric') or '指标'}当前值 {current} 对照规则 {rule.get('operator')} {rule.get('value')}"


def decision_rule_opportunity(rule: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    normalized = evaluation.get("rule") or normalize_rule(rule)
    trigger = normalized.get("trigger_type")
    is_price = trigger in {"price", "price_range"}
    return {
        "rule_id": normalized.get("id"),
        "company_id": normalized.get("company_id"),
        "company": normalized.get("company"),
        "ticker": normalized.get("ticker"),
        "market": normalized.get("market"),
        "currency": normalized.get("currency"),
        "category": normalized.get("category"),
        "trigger_type": trigger,
        "status": evaluation.get("status", "needs_review"),
        "status_label": evaluation.get("status_label"),
        "auto_evaluable": evaluation.get("auto_evaluable") is True,
        "current_value": evaluation.get("current_value"),
        "distance_pct": evaluation.get("distance_pct"),
        "reason": evaluation.get("reason") or normalized.get("description"),
        "description": normalized.get("description"),
        "operator": normalized.get("operator"),
        "value": normalized.get("value"),
        "metric": normalized.get("metric"),
        "event_type": normalized.get("event_type"),
        "action": normalized.get("action"),
        "action_key": normalized.get("action_key"),
        "source": normalized.get("source"),
        "source_report": normalized.get("source_report"),
        "source_section": normalized.get("source_section"),
        "source_text": normalized.get("source_text"),
        "confidence": normalized.get("confidence"),
        "automation": normalized.get("automation"),
        "enabled": normalized.get("enabled") is True,
        "needs_review": normalized.get("needs_review") is True or evaluation.get("status") == "needs_review",
        "list_type": "price" if is_price else "condition",
    }


def opportunity_sort_key(item: dict[str, Any]) -> tuple[int, float, str]:
    status_rank = {
        "triggered": 0,
        "near_trigger": 1,
        "watching": 2,
        "needs_review": 3,
        "inactive": 4,
        "resolved": 5,
        "disabled": 6,
    }
    distance = finite_number(item.get("distance_pct"))
    return (status_rank.get(str(item.get("status")), 9), distance if distance is not None else 999.0, str(item.get("company") or ""))


def drift_rule_status(rule: dict[str, Any], drift: dict[str, Any] | None) -> tuple[str, str | None]:
    """Translate a structured drift result into a rule review signal.

    Drift does not rewrite the rule or place an order.  It only makes a
    condition rule visible as requiring review until a later thesis review
    resolves it.
    """
    normalized = normalize_rule(rule)
    record = drift if isinstance(drift, dict) else {}
    if not normalized["enabled"]:
        return ("needs_review", "迁移候选待人工确认，未启用自动判断") if normalized.get("needs_review") else ("disabled", "规则已禁用")
    if normalized["status"] == "resolved":
        return "resolved", normalized.get("resolution_note") or "规则已解决"
    if (
        normalized["trigger_type"] not in {"price", "price_range"}
        and record.get("direction") == "weakened"
        and record.get("severity") in {"minor", "major"}
    ):
        return "needs_review", "论文漂移已弱化，需运行 Thesis Drift / Review"
    return normalized["status"], None
