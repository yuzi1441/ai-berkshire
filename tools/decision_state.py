#!/usr/bin/env python3
"""Build the structured decision-state compatibility layer.

The existing project deliberately keeps Markdown reports as research truth.
This module adds the small, auditable read model required by the dashboard:
canonical report, Decision Rules, lifecycle, Drift, Event Radar, sentiment,
technical execution and the next action.  It never infers a real holding from
research text; holdings continue to come only from ``post_buy_tracking.json``.
"""

from __future__ import annotations

import hashlib
import json
import re
import copy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from source_hash import canonical_file_sha256
import drift_scan_state


SCHEMA_VERSION = 1
REALTIME_MARKETS = ("A股", "港股")
RULE_TYPES = ("PRICE", "PRICE_RANGE", "METRIC", "EVENT", "ALL_OF", "ANY_OF")
AUTOMATION_LEVELS = ("AUTO", "REVIEW", "MANUAL")
LIFECYCLES = ("WATCH", "PRE_BUY", "HOLDING", "EXITED")
DRIFT_DIRECTIONS = ("improved", "unchanged", "weakened", "unknown")
DRIFT_SEVERITIES = ("none", "minor", "major", "unknown")
RULE_STATUSES = ("triggered", "near_trigger", "not_triggered", "unknown", "needs_review")
RULE_RUNTIME_FIELDS = frozenset({"status", "last_checked"})
PRE_BUY_ACTIONS = frozenset({"run_checklist", "confirm_purchase"})
DRIFT_REVIEW_CATEGORIES = (
    "true_current_drift",
    "new_evidence_other_action",
    "reviewed_not_recognized",
    "never_reviewed",
    "reviewed_current",
    "reviewed_insufficient_evidence",
    "not_applicable",
)
DRIFT_REVIEW_LABELS = {
    "true_current_drift": "需要重新论文漂移复核",
    "new_evidence_other_action": "存在新材料，当前动作不是论文漂移",
    "reviewed_not_recognized": "已复核，但系统未正确识别",
    "never_reviewed": "从未完成论文漂移复核",
    "reviewed_current": "论文已复核，当前有效",
    "reviewed_insufficient_evidence": "论文已复核，但证据不足",
    "not_applicable": "当前生命周期不适用",
}

STATE_RELATIVE = Path("data/investment-dashboard/company_state.json")
RULES_RELATIVE = Path("data/investment-dashboard/decision_rules.json")
TECHNICAL_RELATIVE = Path("data/investment-dashboard/technical_latest.json")
CHECKLIST_RELATIVE = Path("data/investment-dashboard/checklist_states.json")
OVERRIDES_RELATIVE = Path("data/investment-dashboard/company_state_overrides.json")
DRIFT_RELATIVE = Path("data/investment-dashboard/drift_states.json")
DRIFT_SCAN_RELATIVE = drift_scan_state.RELATIVE_PATH
POST_BUY_RELATIVE = Path("data/investment-dashboard/post_buy_tracking.json")

_PRICE_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)(?:\s*[—–-]\s*(\d+(?:\.\d+)?))?(?!\d)")
_WS_RE = re.compile(r"\s+")
_PRICE_WORDS = re.compile(r"(?:价格|股价|元|港元|美元|CNY|HKD|USD|RMB|US\$|HK\$)", re.I)
_EVENT_WORDS = re.compile(
    r"公告|政策|关税|监管|处罚|立案|调查|诉讼|事故|并购|收购|解禁|管理层|任命|辞职|客户|审批|许可|披露|控制权|事件|竞争对手|竞品"
)
_METRIC_WORDS = re.compile(
    r"收入|营收|利润|毛利率|净利率|现金流|自由现金流|ROE|市占|份额|产量|销量|订单|库存|负债|铜价|PE|PB|季度|财报|增速|盈利"
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def rule_definition_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the persisted Rule definition without volatile runtime fields.

    Rule extraction and lifecycle synchronization may write this projection.
    A normal dashboard build must only evaluate a copy into Company State and
    site output; quote/event timestamps never belong in this source of truth.
    """
    result = copy.deepcopy(payload)
    for company in result.get("companies", []) if isinstance(result, dict) else []:
        if not isinstance(company, dict):
            continue
        for rule in company.get("rules", []) or []:
            if not isinstance(rule, dict):
                continue
            for field in RULE_RUNTIME_FIELDS:
                rule.pop(field, None)
            for child in rule.get("children", []) or []:
                if isinstance(child, dict):
                    for field in RULE_RUNTIME_FIELDS:
                        child.pop(field, None)
    return result


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_strict_json(path: Path, *, label: str) -> dict[str, Any]:
    """Load a required state object without silently substituting defaults."""
    if not path.is_file():
        raise ValueError(f"Missing required {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid {label}: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid {label}: expected JSON object: {path}")
    return payload


def validate_rule_definition_payload(payload: dict[str, Any]) -> list[str]:
    """Validate the persisted Rule Definition contract without runtime fields."""
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("decision_rules schema_version")
    if payload.get("rule_types") != list(RULE_TYPES):
        errors.append("decision_rules rule_types")
    companies = payload.get("companies")
    if not isinstance(companies, list) or not companies:
        errors.append("decision_rules companies")
        return errors
    seen: set[str] = set()
    for company in companies:
        if not isinstance(company, dict) or not compact(company.get("ticker")):
            errors.append("decision_rules company ticker")
            continue
        ticker = compact(company.get("ticker")).upper()
        if ticker in seen:
            errors.append(f"duplicate decision_rules company: {ticker}")
        seen.add(ticker)
        if not isinstance(company.get("rules"), list):
            errors.append(f"decision_rules rules: {ticker}")
            continue
        for rule in company["rules"]:
            if not isinstance(rule, dict) or rule.get("type") not in RULE_TYPES:
                errors.append(f"invalid rule type: {ticker}")
    return errors


def load_rule_definitions(path: Path, *, strict: bool = True) -> dict[str, Any]:
    """Load Decision Rule definitions; permissive fallback is opt-in only."""
    if strict:
        payload = load_strict_json(path, label="decision_rules")
        errors = validate_rule_definition_payload(payload)
        if errors:
            raise ValueError("Invalid decision_rules: " + "; ".join(errors))
        return payload
    payload = load_json(path, {})
    return payload if isinstance(payload, dict) else {}


def compact(value: Any) -> str:
    return _WS_RE.sub(" ", str(value or "")).strip()


def company_id(decision: dict[str, Any]) -> str:
    ticker = compact(decision.get("ticker")).upper()
    if ticker:
        return ticker
    market = compact(decision.get("market")) or "UNKNOWN"
    name = compact(decision.get("company")) or "UNKNOWN"
    return f"{market}:{name}"


def canonical_report_hash(decision: dict[str, Any], repo_root: Path) -> str | None:
    """Return the canonical hash of the selected Main Report, if readable.

    This is deliberately separate from the manual-review source fingerprint.
    The latter covers the Main Report, Checklist, and review report together;
    it is not a Main Report identity and must never populate the
    ``canonical_report_sha256`` Company State field.
    """
    report_value = compact(decision.get("report_path"))
    if not report_value:
        return None
    root = repo_root.resolve()
    report_path = (root / report_value).resolve()
    try:
        report_path.relative_to(root)
    except ValueError:
        return None
    if not report_path.is_file():
        return None
    try:
        return canonical_file_sha256(report_path)
    except OSError:
        return None


def confidence(value: Any) -> str:
    text = compact(value).lower()
    if text in {"high", "高"}:
        return "high"
    if text in {"medium", "中"}:
        return "medium"
    if text in {"low", "低"}:
        return "low"
    return "unknown"


def source_section(decision: dict[str, Any], source_field: str | None = None) -> str:
    if source_field == "trigger_condition":
        return "主报告最终决策/买入失效条件"
    if source_field == "empty_position_action":
        return "主报告最终决策/空仓动作"
    if source_field == "holder_action":
        return "主报告最终决策/持仓动作"
    if source_field == "event_condition":
        return "主报告最终决策/买入验证条件"
    if source_field == "guard_condition":
        return "主报告最终决策/失效与减仓条件"
    if decision.get("decision_contract"):
        return "看板决策契约"
    return "主报告最终决策"


def _extract_price(item: dict[str, Any]) -> tuple[float | None, float | None, str]:
    lower = item.get("min")
    upper = item.get("ceiling")
    try:
        low = float(lower) if lower is not None else None
    except (TypeError, ValueError):
        low = None
    try:
        high = float(upper) if upper is not None else None
    except (TypeError, ValueError):
        high = None
    text = compact(item.get("price_range"))
    if low is None and high is None:
        values = _PRICE_RE.findall(text)
        if values:
            low = float(values[0][0])
            high = float(values[0][1]) if values[0][1] else None
    return low, high, text


def _rule_id(ticker: str, rule_type: str, condition: str, source: str) -> str:
    digest = hashlib.sha256(f"{ticker}|{rule_type}|{condition}|{source}".encode("utf-8")).hexdigest()[:12]
    return f"{ticker or 'UNKNOWN'}:{rule_type.lower()}:{digest}"


def _decision_confidence(decision: dict[str, Any]) -> str:
    primary = decision.get("primary_judgment") or {}
    if isinstance(primary, dict) and primary.get("confidence") is not None:
        return confidence(primary.get("confidence"))
    contract = decision.get("decision_contract") or {}
    if isinstance(contract, dict):
        return confidence(contract.get("confidence"))
    return "unknown"


def _price_rule(decision: dict[str, Any], item: dict[str, Any]) -> dict[str, Any] | None:
    low, high, display = _extract_price(item)
    if low is None and high is None:
        return None
    ticker = compact(decision.get("ticker")).upper()
    rule_type = "PRICE_RANGE" if low is not None and high is not None else "PRICE"
    condition = display or compact(item.get("action")) or "价格条件"
    rule = {
        "rule_id": _rule_id(ticker, rule_type, condition, compact(item.get("source") or "price")),
        "type": rule_type,
        "condition": condition,
        "operator": "between" if rule_type == "PRICE_RANGE" else "lte" if high is not None else "gte",
        "min": low,
        "max": high,
        "currency": compact(item.get("currency")) or None,
        "action": "review_decision",
        "automation": "AUTO",
        "status": "unknown",
        "last_checked": None,
        "source_report": decision.get("report_path"),
        "source_section": "主报告估值/行动价格",
        "confidence": _decision_confidence(decision),
        "needs_review": bool(item.get("requires_validation")),
        "source": compact(item.get("source") or "report_price_plan"),
        # The price band is always the entry condition.  A required operating
        # prerequisite is represented separately by event_condition below;
        # do not collapse the two meanings into one Rule.
        "rule_scope": "entry",
    }
    return rule


def _condition_rule(
    decision: dict[str, Any],
    text: Any,
    source_field: str,
    schedule: str | None = None,
    rule_scope: str = "review",
) -> dict[str, Any] | None:
    condition = compact(text)
    if not condition or condition in {"未给出", "无", "待复核", "None"}:
        return None
    # Price fragments are represented by PRICE/PRICE_RANGE.  A condition rule
    # is retained only when there is a non-price reason to recheck the thesis.
    non_price = _PRICE_WORDS.sub(" ", condition).strip(" ，,、；;。")
    if not non_price:
        return None
    rule_type = "EVENT" if _EVENT_WORDS.search(condition) else "METRIC" if _METRIC_WORDS.search(condition) else "EVENT"
    ticker = compact(decision.get("ticker")).upper()
    automation = "REVIEW" if source_field in {"trigger_condition", "empty_position_action"} else "MANUAL"
    rule = {
        "rule_id": _rule_id(ticker, rule_type, condition, source_field),
        "type": rule_type,
        "condition": condition,
        "operator": None,
        "min": None,
        "max": None,
        "currency": None,
        "action": "drop_or_recheck" if rule_scope == "redline" else "run_drift" if rule_scope == "validation" else "review_decision",
        "automation": automation,
        "status": "unknown",
        "last_checked": None,
        "source_report": decision.get("report_path"),
        "source_section": source_section(decision, source_field),
        "confidence": _decision_confidence(decision),
        "needs_review": True,
        "source": source_field,
        "schedule": schedule,
        "rule_scope": rule_scope,
    }
    return rule


def _quote_by_ticker(data_directory: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(data_directory / "quotes" / "latest.json", {})
    return {
        compact(item.get("ticker")).upper(): item
        for item in payload.get("quotes", [])
        if isinstance(item, dict) and compact(item.get("ticker"))
    }


def _quote_price(quote: dict[str, Any] | None) -> float | None:
    if not isinstance(quote, dict):
        return None
    for key in ("price", "latest_price", "close", "last", "current_price"):
        try:
            if quote.get(key) is not None:
                return float(quote[key])
        except (TypeError, ValueError):
            continue
    return None


def _event_text(event: dict[str, Any]) -> str:
    return compact(" ".join(
        str(event.get(key) or "")
        for key in ("headline", "summary", "event_type", "title")
    ))


def _normalise_event_match_text(value: Any) -> str:
    text = compact(value).lower()
    return re.sub(
        r"若|如果|只有|除非|一旦|当|发生|出现|则|需要|启动|运行|重新评估|重新审视|确认|验证|事件|重大",
        "",
        text,
    )


def _event_matches_rule(rule: dict[str, Any], event: dict[str, Any] | None) -> bool:
    """Match a formal event to one Rule, never to the company flag alone."""
    if not isinstance(event, dict):
        return False
    rule_id = rule.get("rule_id")
    for candidate in list(event.get("events") or []) + [event]:
        if not isinstance(candidate, dict):
            continue
        if not bool(candidate.get("thesis_relevant", event.get("thesis_relevant", False))):
            continue
        matched_ids = set()
        for key in ("rule_ids", "matched_rule_ids", "applies_to_rule_ids"):
            values = candidate.get(key) or []
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                matched_ids.update(str(value) for value in values)
        if rule_id and str(rule_id) in matched_ids:
            return True
        condition = _normalise_event_match_text(rule.get("condition"))
        source = _normalise_event_match_text(_event_text(candidate))
        if condition and source and (condition in source or source in condition):
            return True
        condition_tokens = set(re.findall(r"[a-z][a-z0-9+.-]*|[\u4e00-\u9fff]{2,}", condition))
        source_tokens = set(re.findall(r"[a-z][a-z0-9+.-]*|[\u4e00-\u9fff]{2,}", source))
        if condition_tokens and len(condition_tokens) >= 2 and condition_tokens <= source_tokens:
            return True
    return False


def evaluate_rule(
    rule: dict[str, Any],
    quote: dict[str, Any] | None = None,
    event_relevant: bool = False,
    event_context: dict[str, Any] | None = None,
) -> str:
    rule_type = rule.get("type")
    if rule_type in {"PRICE", "PRICE_RANGE"}:
        price = _quote_price(quote)
        if price is None:
            return "unknown"
        low, high = rule.get("min"), rule.get("max")
        try:
            low = float(low) if low is not None else None
            high = float(high) if high is not None else None
        except (TypeError, ValueError):
            return "needs_review"
        if rule_type == "PRICE_RANGE" and low is not None and high is not None:
            if low <= price <= high:
                return "triggered"
            distance = min(abs(price - low) / max(abs(low), 0.01), abs(price - high) / max(abs(high), 0.01))
            return "near_trigger" if distance <= 0.10 else "not_triggered"
        boundary = high if high is not None else low
        if boundary is None:
            return "needs_review"
        triggered = price <= boundary if high is not None else price >= boundary
        distance = abs(price - boundary) / max(abs(boundary), 0.01)
        return "triggered" if triggered else "near_trigger" if distance <= 0.10 else "not_triggered"
    if rule_type == "EVENT":
        if event_context is not None:
            return "triggered" if _event_matches_rule(rule, event_context) else "unknown"
        return "triggered" if event_relevant else "unknown"
    if rule_type == "ALL_OF":
        statuses = [evaluate_rule(child, quote, event_relevant, event_context) for child in rule.get("children", [])]
        if statuses and all(item == "triggered" for item in statuses):
            return "triggered"
        if any(item == "unknown" for item in statuses):
            return "unknown"
        return "not_triggered"
    if rule_type == "ANY_OF":
        statuses = [evaluate_rule(child, quote, event_relevant, event_context) for child in rule.get("children", [])]
        if any(item == "triggered" for item in statuses):
            return "triggered"
        if any(item in {"unknown", "needs_review"} for item in statuses):
            return "unknown"
        return "not_triggered"
    return "unknown"


def _rules_for_decision(decision: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    execution = decision.get("execution_policy") or {}
    for item in execution.get("price_rules") or []:
        if isinstance(item, dict) and (rule := _price_rule(decision, item)):
            rules.append(rule)
    primary = decision.get("primary_judgment") or {}
    # Keep the three executable meanings separate.  ``event_condition`` is
    # the entry/validation gate, while ``guard_condition`` is the redline.
    # Both are already normalized by the existing execution policy; do not
    # split ordinary monitoring prose into artificial rules.
    execution = decision.get("execution_policy") or {}
    if execution.get("event_condition"):
        has_validated_price = any(
            item.get("requires_validation") is True
            for item in execution.get("price_rules") or []
            if isinstance(item, dict)
        )
        if (rule := _condition_rule(
            decision,
            execution.get("event_condition"),
            "event_condition",
            rule_scope="validation" if has_validated_price else "entry",
        )):
            rules.append(rule)
    if execution.get("guard_condition"):
        if (rule := _condition_rule(
            decision,
            execution.get("guard_condition"),
            "guard_condition",
            rule_scope="redline",
        )):
            rules.append(rule)
    if not execution.get("event_condition") and not execution.get("guard_condition"):
        # Legacy/contract-only records may not have an execution policy.  The
        # invalidation field is still a reviewable redline. A primary trigger
        # without a separable guard is retained as validation text rather than
        # silently dropped or mislabelled as a pure redline.
        contract = decision.get("decision_contract") or {}
        if not primary and (rule := _condition_rule(
            decision,
            contract.get("invalidation_triggers"),
            "invalidation_triggers",
            rule_scope="redline",
        )):
            rules.append(rule)
        elif primary and (rule := _condition_rule(
            decision,
            primary.get("trigger_condition"),
            "trigger_condition",
            rule_scope="validation",
        )):
            rules.append(rule)
    unique: dict[str, dict[str, Any]] = {}
    for rule in rules:
        unique[rule["rule_id"]] = rule
    return list(unique.values())


def _checklist_state(decision: dict[str, Any]) -> dict[str, Any]:
    raw = decision.get("checklist") or {}
    value = compact(raw.get("status")).upper()
    if value in {"PASS", "通过", "PASSED"}:
        status = "PASS"
    elif value in {"CONDITIONAL_PASS", "CONDITIONAL PASS", "灰色地带", "条件通过"}:
        status = "CONDITIONAL_PASS"
    elif value in {"FAIL", "未通过", "否决", "FAILED"}:
        status = "FAIL"
    else:
        status = "UNKNOWN"
    return {
        "status": status,
        "hard_veto": raw.get("hard_veto") if raw.get("hard_veto") is not None else None,
        "checked_at": raw.get("checked_at"),
        "summary": raw.get("summary") or None,
        "report_path": raw.get("report_path"),
    }


def _sentiment_by_ticker(data_directory: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(data_directory.parent / "sentiment" / "latest.json", {})
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("companies", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict) or not compact(item.get("ticker")):
            continue
        combined = item.get("combined_sentiment") or {}
        state = compact(combined.get("state")).lower()
        if "负" in state:
            normalized = "negative"
        elif "正" in state or "乐观" in state:
            normalized = "positive"
        elif state:
            normalized = "neutral"
        else:
            normalized = "unknown"
        result[compact(item.get("ticker")).upper()] = {
            "state": normalized,
            "raw_state": combined.get("state"),
            "score": combined.get("score_0_100"),
            "confidence": combined.get("confidence") or "unknown",
            "data_cutoff": payload.get("data_cutoff"),
            "status": payload.get("status") or "unknown",
        }
    return result


def normalize_technical_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    raw_status = raw.get("status") or "unknown"
    data_cutoff = raw.get("data_cutoff")
    requested_cutoff = raw.get("requested_cutoff") or date.today().isoformat()
    freshness = "unknown"
    try:
        freshness = "fresh" if (date.fromisoformat(str(requested_cutoff)) - date.fromisoformat(str(data_cutoff))).days <= 7 else "stale"
    except (TypeError, ValueError):
        pass
    if raw_status not in {"ready", "ok"}:
        return {
            "trend": "UNKNOWN",
            "position": "UNKNOWN",
            "execution": "UNKNOWN",
            "status": raw_status,
            "data_cutoff": data_cutoff,
            "requested_cutoff": requested_cutoff,
            "freshness": freshness,
        }
    if freshness == "stale":
        return {
            "trend": "UNKNOWN",
            "position": "UNKNOWN",
            "execution": "UNKNOWN",
            "status": "review",
            "data_cutoff": data_cutoff,
            "requested_cutoff": requested_cutoff,
            "freshness": freshness,
            "confidence": raw.get("confidence") or "unknown",
            "legacy_state": compact(raw.get("state") or raw.get("technical_state") or raw.get("legacy_state")) or None,
            "observation_zone": raw.get("observation_zone"),
            "indicators": raw.get("lights") or [],
        }
    state = compact(raw.get("state") or raw.get("technical_state") or raw.get("legacy_state"))
    if "防守" in state or "转弱" in state or "风险" in state:
        trend, position, execution = "DOWN", "BROKEN", "UNFAVORABLE"
    elif "分批" in state:
        trend, position, execution = "UP", "NEAR_MEAN", "FAVORABLE"
    elif "回踩" in state:
        trend, position, execution = "UP", "NEAR_MEAN", "NEUTRAL"
    elif "确认" in state:
        trend, position, execution = "UP", "EXTENDED", "NEUTRAL"
    elif "中性" in state:
        trend, position, execution = "NEUTRAL", "NORMAL", "NEUTRAL"
    else:
        trend, position, execution = "UNKNOWN", "UNKNOWN", "UNKNOWN"
    return {
        "trend": trend,
        "position": position,
        "execution": execution,
        "status": raw_status,
        "data_cutoff": data_cutoff,
        "requested_cutoff": requested_cutoff,
        "freshness": freshness,
        "confidence": raw.get("confidence") or "unknown",
        "legacy_state": state or None,
        "observation_zone": raw.get("observation_zone"),
        "indicators": raw.get("lights") or [],
    }


def _technical_state(decision: dict[str, Any], raw_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = raw_snapshot or decision.get("technical_analysis") or {}
    return normalize_technical_state(raw)


def _load_overrides(data_directory: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(data_directory / OVERRIDES_RELATIVE.name, {})
    values = payload.get("companies") if isinstance(payload, dict) else {}
    return values if isinstance(values, dict) else {}


def _load_drift(data_directory: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(data_directory / DRIFT_RELATIVE.name, {})
    values = payload.get("companies") if isinstance(payload, dict) else {}
    return values if isinstance(values, dict) else {}


def _load_drift_scan(data_directory: Path, repo_root: Path) -> dict[str, dict[str, Any]]:
    """Load optional scan checkpoints; a present invalid file fails closed."""
    payload = drift_scan_state.load(data_directory / DRIFT_SCAN_RELATIVE.name, repo_root=repo_root)
    values = payload.get("companies") if isinstance(payload, dict) else {}
    return values if isinstance(values, dict) else {}


def _load_technical_latest(data_directory: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(data_directory / TECHNICAL_RELATIVE.name, {})
    values = (payload.get("companies") or []) if isinstance(payload, dict) else []
    return {
        compact(item.get("ticker")).upper(): item
        for item in values
        if isinstance(item, dict) and compact(item.get("ticker"))
    }


def _tracking_by_ticker(data_directory: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(data_directory / "post_buy_tracking.json", {})
    values = payload.get("positions") if isinstance(payload, dict) else {}
    if not isinstance(values, dict):
        return {}
    result = {str(ticker).upper(): dict(position) for ticker, position in values.items() if isinstance(position, dict)}
    alerts_payload = load_json(data_directory / "post_buy_alerts.json", {})
    for alert in alerts_payload.get("alerts", []) if isinstance(alerts_payload, dict) else []:
        if not isinstance(alert, dict):
            continue
        ticker = compact(alert.get("ticker")).upper()
        if ticker not in result:
            continue
        current = list(result[ticker].get("alerts") or [])
        if alert not in current:
            current.append(alert)
        result[ticker]["alerts"] = current
    return result


def _event_by_ticker(event_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in (event_payload or {}).get("companies", []) if isinstance(event_payload, dict) else []:
        if isinstance(item, dict) and compact(item.get("ticker")):
            result[compact(item.get("ticker")).upper()] = item
    return result


def _drift_value(value: Any, default: str) -> str:
    text = compact(value).lower()
    return text if text in DRIFT_DIRECTIONS or text in DRIFT_SEVERITIES else default


def rule_can_promote_pre_buy(rule: dict[str, Any]) -> bool:
    """Return whether one explicit buy-gate Rule may enter PRE_BUY."""
    if rule.get("status") != "triggered" or rule.get("active", True) is False or rule.get("needs_review"):
        return False
    scope = compact(rule.get("rule_scope")).lower()
    action = compact(rule.get("action")).lower()
    if scope == "entry":
        # Entry is already an explicit buy-progress meaning.  Existing legacy
        # entry records use review_decision; they still require Checklist and
        # never execute a purchase automatically.
        return action in {"review_decision", *PRE_BUY_ACTIONS}
    # A Validation Rule is a gate only when its stored action explicitly says
    # to proceed to the Checklist/purchase confirmation. run_drift and generic
    # review actions must not promote a company.
    return scope == "validation" and (action in PRE_BUY_ACTIONS or rule.get("buy_gate") is True)


def _triggered_redlines(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        rule for rule in rules
        if rule.get("status") == "triggered"
        and rule.get("rule_scope") == "redline"
        and rule.get("active", True) is not False
    ]


def _lifecycle(override: Any, tracking: dict[str, Any] | None, rules: list[dict[str, Any]], checklist: dict[str, Any]) -> tuple[str, str | None]:
    tracking_status = compact((tracking or {}).get("status")).lower()
    if tracking_status in {"holding", "paused"}:
        return "HOLDING", None
    if tracking_status == "closed":
        return "EXITED", None
    requested = compact(override).upper()
    if checklist["status"] == "FAIL":
        return "WATCH", "Checklist FAIL; no automatic purchase or holding transition"
    if _triggered_redlines(rules):
        return "WATCH", "Redline triggered; no PRE_BUY transition"
    if requested in {"WATCH", "PRE_BUY", "EXITED"}:
        return requested, None
    if requested == "HOLDING":
        return "WATCH", "HOLDING requires a registered post-buy position"
    if any(rule_can_promote_pre_buy(rule) for rule in rules):
        return "PRE_BUY", None
    return "WATCH", None


def _next_action(
    lifecycle: str,
    rules: list[dict[str, Any]],
    checklist: dict[str, Any],
    drift: dict[str, Any],
    event: dict[str, Any],
    tracking: dict[str, Any] | None,
    drift_scan: dict[str, Any] | None = None,
) -> str:
    event_state = compact(event.get("state")).lower()
    redlines = _triggered_redlines(rules)
    if any(compact(rule.get("action")).lower() == "run_drift" for rule in redlines):
        return "run_drift"
    if redlines:
        return "drop_or_recheck"
    if lifecycle == "HOLDING":
        if drift.get("direction") == "weakened" and drift.get("severity") == "major":
            return "reduce_review"
        if event_state in {"important", "critical"} and event.get("thesis_relevant"):
            return "run_drift"
        if (tracking or {}).get("alerts"):
            return "review_holding"
        return "hold"
    if lifecycle == "EXITED":
        return "none"
    # An improved thesis is research evidence, not by itself a buy-progress
    # condition.  Let an explicit Entry/buy-validation rule (or the existing
    # PRE_BUY flow below) determine whether the next action is a Checklist.
    # This prevents "the thesis improved" from silently becoming a purchase
    # workflow when price and validation gates are still unknown.
    if drift.get("direction") == "weakened":
        return "drop_or_recheck"
    scan_status = compact((drift_scan or {}).get("status")).lower()
    scan_result = compact((drift_scan or {}).get("result")).lower()
    if lifecycle == "WATCH" and scan_status == "current" and scan_result == "unknown":
        return "drift_recheck"
    if event_state in {"important", "critical"} and event.get("thesis_relevant"):
        # A current unchanged checkpoint covers this exact semantic event and
        # must not keep recreating generic Drift work.  A changed/stale event
        # remains eligible for a new review.
        if not (lifecycle == "WATCH" and scan_status == "current" and scan_result == "unchanged"):
            return "run_drift"
    if checklist["status"] in {"PASS", "CONDITIONAL_PASS"} and lifecycle == "PRE_BUY":
        return "confirm_purchase"
    if lifecycle == "PRE_BUY":
        return "run_checklist"
    if any(
        rule.get("status") == "triggered"
        and rule.get("active", True) is not False
        and compact(rule.get("action")).lower() in {"run_checklist", "review_decision", "confirm_purchase"}
        for rule in rules
    ):
        return "run_checklist"
    if any(rule.get("status") == "near_trigger" for rule in rules if rule.get("type") in {"PRICE", "PRICE_RANGE"}):
        return "price_near_trigger"
    if any(rule.get("status") == "near_trigger" for rule in rules):
        return "condition_near_trigger"
    return "keep_watch"


def classify_drift_review(
    lifecycle: str,
    drift_scan: dict[str, Any] | None,
    drift: dict[str, Any],
    next_action: str,
) -> dict[str, Any]:
    """Classify Drift freshness separately from the company's current action.

    A stale checkpoint means that the evidence fingerprint moved; it does not
    by itself mean that Drift is today's highest-priority action. The current
    action and the existence of a formal review record are used to keep the
    dashboard from turning every new document into a Drift task.
    """
    if lifecycle != "WATCH":
        category = "not_applicable"
    else:
        scan = drift_scan if isinstance(drift_scan, dict) else {}
        status = compact(scan.get("status")).lower() or "missing"
        result = compact(scan.get("result")).lower()
        if status == "stale" and next_action in {"run_drift", "drift_recheck"}:
            category = "true_current_drift"
        elif status == "stale":
            category = "new_evidence_other_action"
        elif status == "current" and result == "unknown":
            category = "reviewed_insufficient_evidence"
        elif status == "current":
            category = "reviewed_current"
        elif status == "missing" and drift.get("last_checked"):
            category = "reviewed_not_recognized"
        elif status == "missing":
            category = "never_reviewed"
        else:
            category = "reviewed_not_recognized"
    scan = drift_scan if isinstance(drift_scan, dict) else {}
    return {
        "category": category,
        "label": DRIFT_REVIEW_LABELS[category],
        "current_action": next_action,
        "checkpoint_status": compact(scan.get("status")).lower() or "missing",
        "checkpoint_result": compact(scan.get("result")).lower() or None,
        "last_checked": drift.get("last_checked"),
    }


def build_drift_review_audit(state_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a machine-readable audit of the dashboard's Drift action mapping."""
    companies = [
        item
        for item in state_payload.get("companies", [])
        if isinstance(item, dict) and item.get("lifecycle") in {"WATCH", "PRE_BUY"}
    ]
    rows: list[dict[str, Any]] = []
    counts = {category: 0 for category in DRIFT_REVIEW_CATEGORIES}
    for item in companies:
        review = item.get("drift_review") or classify_drift_review(
            str(item.get("lifecycle") or ""),
            item.get("drift_scan"),
            item.get("drift") or {},
            str(item.get("next_action") or "keep_watch"),
        )
        category = review.get("category")
        if category not in counts:
            category = "reviewed_not_recognized"
        counts[category] += 1
        rows.append(
            {
                "ticker": item.get("ticker"),
                "company": item.get("company"),
                "market": item.get("market"),
                "lifecycle": item.get("lifecycle"),
                "category": category,
                "label": DRIFT_REVIEW_LABELS[category],
                "current_action": item.get("next_action"),
                "checkpoint_status": review.get("checkpoint_status"),
                "checkpoint_result": review.get("checkpoint_result"),
                "last_checked": review.get("last_checked"),
            }
        )
    rows.sort(key=lambda item: str(item.get("ticker") or ""))
    return {
        "schema_version": 1,
        "scope": {
            "name": "research_pool",
            "lifecycle": ["WATCH", "PRE_BUY"],
            "company_count": len(rows),
        },
        "category_counts": counts,
        "companies": rows,
    }


def _opportunities(rules: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prices: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    for rule in rules:
        item = {
            "rule_id": rule.get("rule_id"),
            "type": rule.get("type"),
            "condition": rule.get("condition"),
            "status": rule.get("status"),
            "automation": rule.get("automation"),
            "confidence": rule.get("confidence"),
        }
        if rule.get("type") in {"PRICE", "PRICE_RANGE"}:
            item.update({"min": rule.get("min"), "max": rule.get("max"), "currency": rule.get("currency")})
            prices.append(item)
        else:
            conditions.append(item)
    return prices, conditions


def build_state_layers(
    decisions: list[dict[str, Any]],
    repo_root: Path,
    *,
    event_payload: dict[str, Any] | None = None,
    rule_payload: dict[str, Any] | None = None,
    write: bool = True,
    generated_at: str | None = None,
    legacy_mode: bool = False,
) -> dict[str, Any]:
    """Evaluate persisted rules; only an explicit legacy mode may infer them."""
    data_directory = repo_root / "data" / "investment-dashboard"
    generated_at = generated_at or now_iso()
    quotes = _quote_by_ticker(data_directory)
    sentiment = _sentiment_by_ticker(data_directory)
    overrides = _load_overrides(data_directory)
    drift_values = _load_drift(data_directory)
    technical_values = _load_technical_latest(data_directory)
    tracking = _tracking_by_ticker(data_directory)
    events = _event_by_ticker(event_payload)
    drift_scan_values = _load_drift_scan(data_directory, repo_root)
    persisted_rules = {
        compact(item.get("ticker")).upper(): item
        for item in (rule_payload or {}).get("companies", [])
        if isinstance(item, dict) and compact(item.get("ticker"))
    }
    rule_companies: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    technical_latest: list[dict[str, Any]] = []
    checklist_states: list[dict[str, Any]] = []
    for decision in decisions:
        ticker = compact(decision.get("ticker")).upper()
        cid = company_id(decision)
        persisted_company = persisted_rules.get(ticker)
        if persisted_company is not None:
            # Decision Rules are produced by the extraction/migration stage.
            # The dashboard build only evaluates their current status and
            # merges them into Company State; it does not reread report prose.
            persisted_rules_all = copy.deepcopy(persisted_company.get("rules") or [])
            # Retired Rules remain in the persisted audit trail, but never
            # enter current status evaluation or active dashboard triggers.
            rules = [rule for rule in persisted_rules_all if rule.get("active", True) is not False]
            retired_rules = [rule for rule in persisted_rules_all if rule.get("active", True) is False]
            retired_rules.extend(copy.deepcopy(persisted_company.get("retired_rules") or []))
            monitoring_metrics = copy.deepcopy(persisted_company.get("monitoring_metrics") or [])
            semantic_review_candidates = copy.deepcopy(persisted_company.get("semantic_review_candidates") or [])
            rule_extraction_status = persisted_company.get("rule_extraction_status")
            zero_rule_reason = persisted_company.get("zero_rule_reason")
            extraction_error = persisted_company.get("extraction_error")
        else:
            if not legacy_mode:
                raise ValueError(f"Missing persisted decision rules for {ticker}")
            # Compatibility fallback for explicit migration/test/legacy calls.
            rules = _rules_for_decision(decision)
            monitoring_metrics = []
            semantic_review_candidates = []
            rule_extraction_status = "structured_extracted" if rules else "extraction_not_run"
            zero_rule_reason = None if rules else None
            extraction_error = None
            retired_rules = []
        realtime_supported = decision.get("market") in REALTIME_MARKETS
        event_source_status = compact(
            (event_payload or {}).get("source_status")
            if isinstance(event_payload, dict)
            else ""
        ).lower() or "unavailable"
        event = events.get(
            ticker,
            {
                "state": "unknown",
                "thesis_relevant": False,
                "events": [],
                "source_status": event_source_status,
            },
        )
        event = dict(event)
        event_source_status = compact(event.get("source_status")).lower() or "unknown"
        if (
            realtime_supported
            and event.get("state") == "normal"
            and event_source_status not in {"ok", "complete", "success"}
        ):
            event["state"] = "unknown"
        quote = quotes.get(ticker)
        for rule in rules:
            event_triggered = bool(event.get("thesis_relevant")) and event.get("state") in {"important", "critical"}
            rule["status"] = evaluate_rule(rule, quote, event_triggered, event)
            rule["last_checked"] = generated_at
        checklist = _checklist_state(decision)
        drift_raw = drift_values.get(ticker) or drift_values.get(cid) or {}
        drift = {
            "mode": "holding" if compact((tracking.get(ticker) or {}).get("status")).lower() in {"holding", "paused", "closed"} else "watch",
            "direction": _drift_value(drift_raw.get("direction"), "unknown"),
            "severity": _drift_value(drift_raw.get("severity"), "none"),
            "last_checked": drift_raw.get("last_checked"),
            "next_review": drift_raw.get("next_review"),
            "summary": drift_raw.get("summary"),
            "source": drift_raw.get("source"),
        }
        lifecycle, warning = _lifecycle((overrides.get(ticker) or {}).get("lifecycle"), tracking.get(ticker), rules, checklist)
        technical = _technical_state(decision, technical_values.get(ticker))
        if not realtime_supported:
            sentiment_item = {
                "state": "unknown",
                "confidence": "unknown",
                "status": "unknown",
                "realtime_scope": "research_only",
            }
        else:
            sentiment_item = dict(
                sentiment.get(ticker, {"state": "unknown", "confidence": "unknown", "status": "unknown"})
            )
            sentiment_item.setdefault("realtime_scope", "supported")
        technical["realtime_scope"] = "supported" if realtime_supported else "research_only"
        if not realtime_supported:
            technical["freshness"] = "not_applicable"
        event_realtime_scope = "supported" if realtime_supported else "research_only"
        prices, conditions = _opportunities(rules)
        intraday_eligible = lifecycle == "PRE_BUY" and checklist["status"] in {"PASS", "CONDITIONAL_PASS"}
        technical["intraday_eligible"] = intraday_eligible
        report_hash = canonical_report_hash(decision, repo_root)
        checkpoint = drift_scan_values.get(ticker)
        checkpoint_evidence_sha = (
            checkpoint.get("research_evidence_sha256")
            if isinstance(checkpoint, dict)
            else None
        )
        current_trigger_fingerprint = drift_scan_state.trigger_fingerprint(
            ticker,
            report_hash,
            [*rules, *retired_rules],
            event,
            research_evidence_sha256=checkpoint_evidence_sha,
        )
        drift_scan = drift_scan_state.project_checkpoint(
            checkpoint,
            mode=(
                "watch"
                if lifecycle == "WATCH"
                else "holding"
                if drift["mode"] == "holding"
                else "not_applicable"
            ),
            baseline_report_sha256=report_hash,
            current_trigger_fingerprint=current_trigger_fingerprint,
        )
        next_action = _next_action(
            lifecycle, rules, checklist, drift, event, tracking.get(ticker), drift_scan
        )
        drift_review = classify_drift_review(lifecycle, drift_scan, drift, next_action)
        state = {
            "company_id": cid,
            "company": decision.get("company"),
            "ticker": ticker or None,
            "market": decision.get("market") or "unknown",
            "realtime_scope": "supported" if decision.get("market") in REALTIME_MARKETS else "research_only",
            "lifecycle": lifecycle,
            "canonical_report": decision.get("report_path") or None,
            "canonical_report_sha256": report_hash,
            "manual_review_source_fingerprint_sha256": decision.get("source_fingerprint_sha256") or None,
            "decision_rules": {
                "total": len(rules),
                "triggered": sum(rule.get("status") == "triggered" for rule in rules),
                "near_trigger": sum(rule.get("status") == "near_trigger" for rule in rules),
                "needs_review": sum(bool(rule.get("needs_review")) for rule in rules),
                "semantic_review_count": len(semantic_review_candidates),
                "extraction_status": rule_extraction_status,
                "zero_rule_reason": zero_rule_reason,
                "monitoring_metrics": monitoring_metrics,
                "semantic_review_candidates": semantic_review_candidates,
                "rules": rules,
                "retired_rules": retired_rules,
            },
            "drift": drift,
            "drift_scan": drift_scan,
            "drift_review": drift_review,
            "event_radar": {
                "state": event.get("state", "unknown"),
                "thesis_relevant": bool(event.get("thesis_relevant")),
                "event_count": len(event.get("events") or []),
                "recommended_action": event.get("recommended_action", "none"),
                "last_checked": event.get("last_checked"),
                "data_cutoff": event.get("data_cutoff"),
                "events": event.get("events") or [],
                "source_status": event_source_status,
                "realtime_scope": event_realtime_scope,
            },
            "sentiment": sentiment_item,
            "technical": technical,
            "checklist": checklist,
            "price_opportunities": prices,
            "condition_opportunities": conditions,
            "opportunity_type": "both" if prices and conditions else "price" if prices else "condition" if conditions else "none",
            "next_action": next_action,
            "needs_attention": next_action not in {"keep_watch", "hold", "none"} or lifecycle == "PRE_BUY",
            "warning": warning,
            "post_buy_tracking": tracking.get(ticker) if tracking.get(ticker) else {"status": "not_tracked"},
            "generated_at": generated_at,
        }
        states.append(state)
        rule_summary = state["decision_rules"].copy()
        rule_summary["rules"] = None
        rule_companies.append({
            "company_id": cid,
            "company": decision.get("company"),
            "ticker": ticker or None,
            "market": decision.get("market") or "unknown",
            "realtime_scope": "supported" if decision.get("market") in REALTIME_MARKETS else "research_only",
            "canonical_report": decision.get("report_path") or None,
            "rules": rules,
            "retired_rules": retired_rules,
            "monitoring_metrics": monitoring_metrics,
            "semantic_review_candidates": semantic_review_candidates,
            "rule_extraction_status": rule_extraction_status,
            "zero_rule_reason": zero_rule_reason,
            "extraction_error": extraction_error,
            "summary": rule_summary,
        })
        technical_latest.append({"company_id": cid, "company": decision.get("company"), "ticker": ticker or None, "market": decision.get("market"), **technical})
        checklist_states.append({"company_id": cid, "company": decision.get("company"), "ticker": ticker or None, "market": decision.get("market"), **checklist})

    rules_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "rule_types": list(RULE_TYPES),
        "automation_levels": list(AUTOMATION_LEVELS),
        "companies": rule_companies,
        "rule_count": sum(len(item.get("rules") or []) for item in rule_companies),
        "retired_rule_count": sum(len(item.get("retired_rules") or []) for item in rule_companies),
        "quality_dimensions": {
            "extraction_confidence": "rules[].confidence (structured/semantic extraction quality; not action automation)",
            "automation_level": "rules[].automation (AUTO/REVIEW/MANUAL execution capability)",
            "current_rule_status": "rules[].status (current facts/quote evaluation)",
            "rule_manual_review_flag": "rules[].needs_review (legacy per-rule operational review flag)",
            "semantic_review_queue": "companies[].semantic_review_candidates (body meaning not safely normalized)",
            "zero_rule_reason": "companies[].zero_rule_reason (only when rules is empty)",
        },
    }
    if rule_payload:
        for key in ("extraction_policy", "zero_rule_audit", "quality_dimensions", "scope_summary", "lifecycle_policy"):
            if key in rule_payload:
                rules_payload[key] = copy.deepcopy(rule_payload[key])
        if rule_payload.get("generated_at"):
            rules_payload["extraction_generated_at"] = rule_payload["generated_at"]
    state_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "lifecycle_states": list(LIFECYCLES),
        "company_count": len(states),
        "companies": states,
        "summary": {state: sum(item.get("lifecycle") == state for item in states) for state in LIFECYCLES},
        "attention_count": sum(bool(item.get("needs_attention")) for item in states),
    }
    technical_payload = {"schema_version": SCHEMA_VERSION, "generated_at": generated_at, "companies": technical_latest}
    checklist_payload = {"schema_version": SCHEMA_VERSION, "generated_at": generated_at, "companies": checklist_states}
    result = {
        "rules": rules_payload,
        "state": state_payload,
        "technical": technical_payload,
        "checklist": checklist_payload,
        "drift_review_audit": build_drift_review_audit(state_payload),
    }
    if write:
        # Rule definitions are written only by extraction/lifecycle commands.
        # This build-time projection contains volatile statuses and timestamps.
        write_json(data_directory / STATE_RELATIVE.name, state_payload)
        write_json(data_directory / TECHNICAL_RELATIVE.name, technical_payload)
        write_json(data_directory / CHECKLIST_RELATIVE.name, checklist_payload)
    return result


def attach_company_states(decisions: list[dict[str, Any]], state_payload: dict[str, Any]) -> None:
    by_ticker = {compact(item.get("ticker")).upper(): item for item in state_payload.get("companies", []) if isinstance(item, dict)}
    for decision in decisions:
        ticker = compact(decision.get("ticker")).upper()
        state = by_ticker.get(ticker)
        if state:
            # Keep the board small.  Full rules/events stay in the dedicated
            # state file; these two fields are compatibility hints only.
            decision["company_state_ref"] = "data/investment-dashboard/company_state.json"
            decision["lifecycle"] = state.get("lifecycle")
            decision["next_action"] = state.get("next_action")


def validate_payloads(payloads: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rules = payloads.get("rules") or {}
    state = payloads.get("state") or {}
    if rules.get("schema_version") != SCHEMA_VERSION:
        errors.append("decision_rules schema_version")
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append("company_state schema_version")
    if rules.get("rule_types") != list(RULE_TYPES):
        errors.append("decision_rules rule_types")
    scan = payloads.get("drift_scan")
    if scan is not None:
        errors.extend(f"{error}" for error in drift_scan_state.validate_payload(scan))
    for item in state.get("companies", []):
        if item.get("lifecycle") not in LIFECYCLES:
            errors.append(f"invalid lifecycle: {item.get('ticker')}")
        scan = item.get("drift_scan")
        if isinstance(scan, dict):
            scan_status = compact(scan.get("status")).lower()
            if scan_status not in drift_scan_state.SCAN_STATUSES:
                errors.append(f"invalid drift scan status: {item.get('ticker')}")
            scan_result = scan.get("result")
            if scan_result is not None and compact(scan_result).lower() not in drift_scan_state.SCAN_RESULTS:
                errors.append(f"invalid drift scan result: {item.get('ticker')}")
            for field in ("baseline_report_sha256", "trigger_fingerprint", "current_trigger_fingerprint"):
                value = scan.get(field)
                if value and not drift_scan_state.is_sha256(value):
                    errors.append(f"invalid drift scan {field}: {item.get('ticker')}")
        for rule in (item.get("decision_rules") or {}).get("rules", []):
            if rule.get("type") not in RULE_TYPES:
                errors.append(f"invalid rule type: {rule.get('rule_id')}")
            if rule.get("automation") not in AUTOMATION_LEVELS:
                errors.append(f"invalid automation: {rule.get('rule_id')}")
            if rule.get("status") not in RULE_STATUSES:
                errors.append(f"invalid rule status: {rule.get('rule_id')}")
    return errors
