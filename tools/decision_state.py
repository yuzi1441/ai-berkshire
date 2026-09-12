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
import math
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from source_hash import canonical_file_sha256
import drift_scan_state
import investment_dispositions
import light_thesis_signals
import financial_facts


SCHEMA_VERSION = 1
REALTIME_MARKETS = ("A股", "港股")
RULE_TYPES = ("PRICE", "PRICE_RANGE", "METRIC", "EVENT", "ALL_OF", "ANY_OF")
AUTOMATION_LEVELS = ("AUTO", "REVIEW", "MANUAL")
LIFECYCLES = ("WATCH", "PRE_BUY", "HOLDING", "EXITED")
DRIFT_DIRECTIONS = ("improved", "unchanged", "weakened", "unknown")
DRIFT_SEVERITIES = ("none", "minor", "major", "unknown")
RULE_STATUSES = (
    "triggered", "near_trigger", "not_triggered", "unknown", "needs_review",
    "invalid_definition", "data_error",
)
RULE_RUNTIME_FIELDS = frozenset({"status", "last_checked", "evaluation"})
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
GUIDANCE_PRIORITIES = ("urgent", "normal", "monitor", "none")
CANONICAL_SKILLS_DIRECTORY = Path(__file__).resolve().parent.parent / "skills"

STATE_RELATIVE = Path("data/investment-dashboard/company_state.json")
RULES_RELATIVE = Path("data/investment-dashboard/decision_rules.json")
TECHNICAL_RELATIVE = Path("data/investment-dashboard/technical_latest.json")
CHECKLIST_RELATIVE = Path("data/investment-dashboard/checklist_states.json")
EVALUATIONS_RELATIVE = Path("data/investment-dashboard/rule_evaluations.json")
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
_COMPOSITE_PRICE_WORDS = re.compile(
    r"中报|年报|季报|业绩|转负面|转正面|经营|订单|现金流|FCF|毛利率|收入|利润|公告|事件",
    re.I,
)
_NON_EQUITY_PRICE_WORDS = re.compile(
    r"亿元|万元|百万元|收入|营收|利润|现金流|FCF|净现金|批价|铝价|铜价|煤价|油价|"
    r"产品价格|产品单价|元/吨|元/瓶|元/瓦|元/Wh|美元/吨",
    re.I,
)
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_iso_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp for ordering without relying on text layout."""
    text = compact(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI_TIMEZONE)
    return parsed


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
    market_snapshots = payload.get("market_snapshots")
    if not isinstance(market_snapshots, dict):
        market_snapshots = {}
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("quotes", []):
        if not isinstance(item, dict) or not compact(item.get("ticker")):
            continue
        quote = dict(item)
        market = compact(item.get("market"))
        market_snapshot = market_snapshots.get(market)
        if not isinstance(market_snapshot, dict):
            market_snapshot = {
                "market": market,
                "quote_type": payload.get("quote_phase"),
                "source_status": payload.get("source_status"),
                "refresh_status": "legacy_snapshot",
                "data_cutoff": payload.get("data_cutoff"),
                "last_success_at": payload.get("generated_at"),
            }
        quote["_market_snapshot"] = market_snapshot
        result[compact(item.get("ticker")).upper()] = quote
    return result


def _quote_price(quote: dict[str, Any] | None) -> float | None:
    if not isinstance(quote, dict):
        return None
    for key in ("price", "latest_price", "close", "last", "current_price"):
        try:
            if quote.get(key) is not None:
                value = float(quote[key])
                return value if math.isfinite(value) and value > 0 else None
        except (TypeError, ValueError):
            continue
    return None


def quote_observed_at(quote: dict[str, Any]) -> datetime | None:
    """Provider observation time, never the time an old snapshot was rebuilt."""
    value = compact(quote.get("provider_timestamp"))
    for pattern in ("%Y%m%d%H%M%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=SHANGHAI_TIMEZONE)
        except ValueError:
            pass
    return None


def _market_is_open(market: str, current: datetime) -> bool:
    local = current.astimezone(SHANGHAI_TIMEZONE)
    if local.weekday() >= 5:
        return False
    clock = local.time().replace(tzinfo=None)
    if market == "A股":
        return time(9, 30) <= clock <= time(11, 30) or time(13, 0) <= clock <= time(15, 0)
    if market == "港股":
        return time(9, 30) <= clock <= time(12, 0) or time(13, 0) <= clock <= time(16, 0)
    return False


def _quote_trust(quote: dict[str, Any] | None, evaluated_at: datetime) -> tuple[bool, str]:
    if not isinstance(quote, dict) or _quote_price(quote) is None:
        return False, "quote_missing"
    if quote.get("snapshot_status") == "preserved_previous":
        return False, "quote_missing_from_latest_refresh"
    metadata = quote.get("_market_snapshot")
    if not isinstance(metadata, dict):
        return True, "direct_quote_without_snapshot_metadata"
    if metadata.get("refresh_status") == "failed" or metadata.get("source_status") == "unavailable":
        return False, "market_refresh_failed"
    data_cutoff = compact(quote.get("data_cutoff") or metadata.get("data_cutoff"))
    market = compact(quote.get("market") or metadata.get("market"))
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", data_cutoff):
        return False, "quote_date_missing"
    if _market_is_open(market, evaluated_at) and data_cutoff != evaluated_at.astimezone(SHANGHAI_TIMEZONE).date().isoformat():
        return False, "historical_close_during_trading_session"
    observed_at = quote_observed_at(quote)
    if observed_at is None:
        return False, "quote_timestamp_missing"
    age_minutes = (evaluated_at - observed_at).total_seconds() / 60
    if age_minutes < -2:
        return False, "quote_timestamp_in_future"
    if _market_is_open(market, evaluated_at) and age_minutes > 10:
        return False, "quote_stale_during_trading_session"
    return True, "quote_current_for_market_session"


def _unparsed_price_composite(rule: dict[str, Any]) -> bool:
    condition = compact(rule.get("condition"))
    if not condition:
        return False
    return bool(_COMPOSITE_PRICE_WORDS.search(condition) and re.search(r"且|并且|同时|前提|后再|后可|未转|转正", condition))


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
    """Compatibility wrapper returning only the current Evaluation result."""
    return evaluate_rule_result(rule, quote, event_relevant, event_context)["result"]


def _apply_condition_review(
    base: dict[str, Any], condition_review: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not isinstance(condition_review, dict):
        return None
    review = condition_review.get("review") or {}
    if condition_review.get("mapping_status") == "ambiguous":
        base.update({
            "result": "unknown",
            "evidence_source": "human_locked_manual_review",
            "evidence_date": review.get("latest_evidence_date"),
            "reason": "ambiguous_review_mapping",
        })
        return base
    reviewed = condition_review.get("result") or {}
    definition = condition_review.get("definition") or {}
    truth_state = compact(reviewed.get("truth_state")).lower()
    if truth_state not in {"met", "not_met", "unknown", "not_due"}:
        return None
    if review.get("freshness") != "current":
        base.update({
            "result": "unknown",
            "actual_value": reviewed.get("current_value"),
            "period": definition.get("periods") or None,
            "evidence_source": "human_locked_manual_review",
            "evidence_date": review.get("latest_evidence_date") or review.get("reviewed_at"),
            "reason": "stale_human_review",
            "review_reason": reviewed.get("reason"),
            "reviewed_at": review.get("reviewed_at"),
            "last_evidence_probe_at": review.get("last_probe_at"),
            "latest_relevant_evidence_at": review.get("latest_relevant_evidence_at"),
            "evidence_fingerprint": review.get("evidence_fingerprint"),
            "source_review_rule_id": definition.get("rule_id"),
        })
        return base
    result = {
        "met": "triggered",
        "not_met": "not_triggered",
        "unknown": "unknown",
        "not_due": "unknown",
    }[truth_state]
    reason = {
        "met": "reviewed_condition_met",
        "not_met": "reviewed_condition_not_met",
        "unknown": "reviewed_evidence_insufficient",
        "not_due": "awaiting_scheduled_evidence",
    }[truth_state]
    base.update({
        "result": result,
        "actual_value": reviewed.get("current_value"),
        "period": definition.get("periods") or None,
        "evidence_source": "human_locked_manual_review",
        "evidence_date": review.get("latest_evidence_date") or review.get("reviewed_at"),
        "reason": reason,
        "review_reason": reviewed.get("reason"),
        "reviewed_at": review.get("reviewed_at"),
        "evidence_fingerprint": review.get("evidence_fingerprint"),
        "evidence_quality": review.get("evidence_quality"),
        "last_evidence_probe_at": review.get("last_probe_at"),
        "source_review_rule_id": definition.get("rule_id"),
        "missing_codes": reviewed.get("missing_codes") or [],
    })
    return base


def evaluate_rule_result(
    rule: dict[str, Any],
    quote: dict[str, Any] | None = None,
    event_relevant: bool = False,
    event_context: dict[str, Any] | None = None,
    condition_review: dict[str, Any] | None = None,
    *,
    evaluated_at: str | None = None,
    financial_fact: dict[str, Any] | None = None,
    condition_review_resolver: Any = None,
    financial_fact_resolver: Any = None,
) -> dict[str, Any]:
    """Evaluate one definition into an auditable, non-authoritative result."""
    evaluated_text = evaluated_at or now_iso()
    try:
        evaluated_datetime = datetime.fromisoformat(evaluated_text)
    except ValueError:
        evaluated_datetime = datetime.now().astimezone()
    base = {
        "rule_id": rule.get("rule_id"),
        "result": "unknown",
        "actual_value": None,
        "period": None,
        "evidence_source": None,
        "evidence_date": None,
        "market_data_cutoff": None,
        "evaluated_at": evaluated_text,
        "reason": "no deterministic evaluator",
    }
    rule_type = rule.get("type")
    if rule_type in {"PRICE", "PRICE_RANGE"}:
        price = _quote_price(quote)
        metadata = quote.get("_market_snapshot") if isinstance(quote, dict) else {}
        trusted, trust_reason = _quote_trust(quote, evaluated_datetime)
        base.update({
            "actual_value": price,
            "evidence_source": quote.get("source") if isinstance(quote, dict) else None,
            "evidence_date": quote.get("data_cutoff") if isinstance(quote, dict) else None,
            "market_data_cutoff": quote.get("data_cutoff") if isinstance(quote, dict) else None,
            "quote_type": metadata.get("quote_type") if isinstance(metadata, dict) else None,
            "refresh_status": metadata.get("refresh_status") if isinstance(metadata, dict) else None,
        })
        if not trusted:
            base.update({"result": "data_error", "reason": trust_reason})
            return base
        if _unparsed_price_composite(rule):
            base.update({"result": "unknown", "reason": "composite_condition_not_structured"})
            return base
        if _NON_EQUITY_PRICE_WORDS.search(compact(rule.get("condition"))):
            base.update({"result": "unknown", "reason": "non_equity_price_condition_not_structured"})
            return base
        low, high = rule.get("min"), rule.get("max")
        try:
            low = float(low) if low is not None else None
            high = float(high) if high is not None else None
        except (TypeError, ValueError):
            base.update({"result": "invalid_definition", "reason": "invalid_price_boundary"})
            return base
        if rule_type == "PRICE_RANGE" and low is not None and high is not None:
            if low <= price <= high:
                result = "triggered"
            else:
                distance = min(abs(price - low) / max(abs(low), 0.01), abs(price - high) / max(abs(high), 0.01))
                result = "near_trigger" if distance <= 0.10 else "not_triggered"
            base.update({"result": result, "reason": "price_range_evaluated"})
            return base
        boundary = high if high is not None else low
        if boundary is None:
            base.update({"result": "invalid_definition", "reason": "missing_price_boundary"})
            return base
        triggered = price <= boundary if high is not None else price >= boundary
        distance = abs(price - boundary) / max(abs(boundary), 0.01)
        base.update({
            "result": "triggered" if triggered else "near_trigger" if distance <= 0.10 else "not_triggered",
            "reason": "price_boundary_evaluated",
        })
        return base
    if rule_type == "EVENT":
        if event_context is not None:
            matched = _event_matches_rule(rule, event_context)
            reviewed_result = None if matched else _apply_condition_review(base, condition_review)
            if reviewed_result is not None:
                return reviewed_result
            base.update({
                "result": "triggered" if matched else "unknown",
                "evidence_source": event_context.get("source") or "event_radar",
                "evidence_date": event_context.get("data_cutoff") or event_context.get("last_checked"),
                "reason": "event_matched" if matched else "awaiting_event_confirmation",
            })
            return base
        if not event_relevant:
            reviewed_result = _apply_condition_review(base, condition_review)
            if reviewed_result is not None:
                return reviewed_result
        base.update({
            "result": "triggered" if event_relevant else "unknown",
            "reason": "event_relevant" if event_relevant else "awaiting_event_confirmation",
        })
        return base
    if rule_type == "METRIC":
        reviewed_result = _apply_condition_review(base, condition_review)
        if reviewed_result is not None:
            return reviewed_result
        required = ("metric", "operator", "threshold", "period", "unit")
        if any(rule.get(field) in (None, "") for field in required):
            base["reason"] = "missing_computable_definition"
            return base
        if not isinstance(financial_fact, dict) or financial_fact.get("resolution_status") == "missing":
            base.update({"result": "data_error", "reason": "financial_fact_missing"})
            return base
        if financial_fact.get("resolution_status") == "conflict":
            base.update({"result": "data_error", "reason": "financial_fact_conflict"})
            return base
        if financial_fact.get("unit") != rule.get("unit"):
            base.update({"result": "data_error", "reason": "financial_fact_unit_mismatch"})
            return base
        try:
            actual = Decimal(str(financial_fact.get("actual_value")))
            threshold = Decimal(str(rule.get("threshold")))
            valid_until = date.fromisoformat(str(financial_fact.get("valid_until")))
        except (InvalidOperation, ValueError):
            base.update({"result": "data_error", "reason": "financial_fact_invalid"})
            return base
        if not actual.is_finite() or not threshold.is_finite():
            base.update({"result": "data_error", "reason": "financial_fact_invalid"})
            return base
        if valid_until < evaluated_datetime.astimezone(SHANGHAI_TIMEZONE).date():
            base.update({"result": "data_error", "reason": "financial_fact_stale"})
            return base
        operator = str(rule.get("operator"))
        comparisons = {
            ">": lambda: actual > threshold,
            ">=": lambda: actual >= threshold,
            "<": lambda: actual < threshold,
            "<=": lambda: actual <= threshold,
            "==": lambda: actual == threshold,
            "!=": lambda: actual != threshold,
        }
        if operator not in comparisons:
            base.update({"result": "invalid_definition", "reason": "unsupported_metric_operator"})
            return base
        base.update({
            "result": "triggered" if comparisons[operator]() else "not_triggered",
            "actual_value": str(actual),
            "threshold": str(threshold),
            "operator": operator,
            "unit": rule.get("unit"),
            "period": financial_fact.get("period"),
            "evidence_source": financial_fact.get("evidence_source"),
            "source_identity": financial_fact.get("source_identity"),
            "evidence_date": financial_fact.get("evidence_date"),
            "content_sha256": financial_fact.get("content_sha256"),
            "reason": "metric_evaluated",
        })
        return base
    if rule_type in {"ALL_OF", "ANY_OF"}:
        children = rule.get("children")
        if not isinstance(children, list) or not children:
            base.update({"result": "invalid_definition", "reason": "empty_composite_children", "children": []})
            return base
        child_results = [
            evaluate_rule_result(
                child,
                quote,
                event_relevant,
                event_context,
                condition_review_resolver(child) if condition_review_resolver else None,
                evaluated_at=evaluated_text,
                financial_fact=financial_fact_resolver(child) if financial_fact_resolver else None,
                condition_review_resolver=condition_review_resolver,
                financial_fact_resolver=financial_fact_resolver,
            )
            for child in children
        ]
        statuses = [item["result"] for item in child_results]
        if rule_type == "ALL_OF":
            if "not_triggered" in statuses:
                result = "not_triggered"
            elif all(item == "triggered" for item in statuses):
                result = "triggered"
            else:
                result = "unknown"
        else:
            if "triggered" in statuses:
                result = "triggered"
            elif all(item == "not_triggered" for item in statuses):
                result = "not_triggered"
            else:
                result = "unknown"
        base.update({"result": result, "reason": f"{rule_type.lower()}_aggregated", "children": child_results})
        return base
    return base


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
    if raw.get("freshness") == "stale" or raw_status == "stale":
        freshness = "stale"
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


def _load_condition_reviews(
    data_directory: Path,
    current_review_payload: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load exact, human-locked condition results as evaluation evidence.

    These files already exist as Git-authoritative research artifacts. They do
    not redefine Decision Rules: a result is eligible only when its reviewed
    Main Report hash still matches and one active human-locked condition maps
    exactly to one persisted Rule condition.
    """
    payload = load_json(data_directory / "codex_direct_manual_review.json", {})
    reviews = {
        compact(item.get("ticker")).upper(): item
        for item in payload.get("reviews", [])
        if isinstance(item, dict) and compact(item.get("ticker"))
    }
    if current_review_payload is None:
        current_review_payload = load_json(data_directory / "main_report_review.json", {})
    current_reviews = {
        compact(item.get("ticker")).upper(): item
        for item in current_review_payload.get("reviews", [])
        if isinstance(item, dict) and compact(item.get("ticker"))
    }
    result: dict[str, dict[str, Any]] = {}
    rules_directory = data_directory / "main-report-review-rules"
    for ticker, review in reviews.items():
        package = load_json(rules_directory / f"{ticker}.json", {})
        if (package.get("authority_policy") or {}).get("active_authority") != "human_locked":
            continue
        package_hash = compact((package.get("main_report") or {}).get("canonical_sha256"))
        review_hash = compact((review.get("main_report") or {}).get("canonical_sha256"))
        if not package_hash or package_hash != review_hash:
            continue
        review_results = {
            compact(item.get("rule_id")): item
            for item in review.get("rule_results", [])
            if isinstance(item, dict) and compact(item.get("rule_id"))
        }
        current_review = current_reviews.get(ticker) or {}
        strict_incremental = (
            (current_review.get("routine") or {}).get("strict_incremental") or {}
        )
        last_probe_at = current_review.get("last_probe_at")
        reviewed_at = review.get("reviewed_at")
        last_probe_datetime = _parse_iso_datetime(last_probe_at)
        reviewed_datetime = _parse_iso_datetime(reviewed_at)
        freshness = "unverified"
        if (
            compact(strict_incremental.get("status")) == "waiting_evidence"
            and strict_incremental.get("current_evidence_count") == 0
            and last_probe_datetime is not None
            and reviewed_datetime is not None
            and last_probe_datetime >= reviewed_datetime
        ):
            freshness = "current"
        elif strict_incremental.get("current_evidence_count"):
            freshness = "new_evidence"
        elif compact(strict_incremental.get("status")):
            freshness = "stale"
        by_condition: dict[str, list[dict[str, Any]]] = {}
        by_rule_id: dict[str, list[dict[str, Any]]] = {}
        for definition in package.get("active_rules", []):
            if not isinstance(definition, dict) or definition.get("authority") != "human_locked":
                continue
            reviewed = review_results.get(compact(definition.get("rule_id")))
            condition = compact(definition.get("condition"))
            if reviewed is None or not condition:
                continue
            mapped = {
                "definition": definition,
                "result": reviewed,
            }
            by_condition.setdefault(condition, []).append(mapped)
            by_rule_id.setdefault(compact(definition.get("rule_id")), []).append(mapped)
        result[ticker] = {
            "baseline_report_sha256": package_hash,
            "reviewed_at": review.get("reviewed_at"),
            "latest_evidence_date": review.get("latest_evidence_date"),
            "evidence_fingerprint": review.get("evidence_fingerprint"),
            "evidence_quality": review.get("evidence_quality"),
            "freshness": freshness,
            "last_probe_at": last_probe_at,
            "latest_relevant_evidence_at": strict_incremental.get("latest_evidence_date"),
            "by_condition": by_condition,
            "by_rule_id": by_rule_id,
        }
    return result


def _condition_review_for_rule(
    company_review: dict[str, Any] | None,
    rule: dict[str, Any],
    report_hash: str | None,
) -> dict[str, Any] | None:
    if not isinstance(company_review, dict):
        return None
    if not report_hash or company_review.get("baseline_report_sha256") != report_hash:
        return None
    rule_id = compact(rule.get("rule_id"))
    matches = (company_review.get("by_rule_id") or {}).get(rule_id, []) if rule_id else []
    if not matches:
        matches = (company_review.get("by_condition") or {}).get(compact(rule.get("condition")), [])
    if len(matches) > 1:
        return {"mapping_status": "ambiguous", "review": company_review}
    if len(matches) != 1:
        return None
    return {**matches[0], "mapping_status": "exact", "review": company_review}


def _load_drift_scan(data_directory: Path, repo_root: Path) -> dict[str, dict[str, Any]]:
    """Load optional scan checkpoints; a present invalid file fails closed."""
    payload = drift_scan_state.load(data_directory / DRIFT_SCAN_RELATIVE.name, repo_root=repo_root)
    values = payload.get("companies") if isinstance(payload, dict) else {}
    return values if isinstance(values, dict) else {}


def _load_technical_latest(data_directory: Path) -> dict[str, dict[str, Any]]:
    path = data_directory / "technical_daily_snapshot.json"
    payload = load_json(path, {})
    if not payload:
        legacy = load_json(data_directory / TECHNICAL_RELATIVE.name, {})
        # The old path mixed raw acquisition and rebuildable projections.
        # Only an actual batch output is eligible as acquisition authority.
        payload = legacy if legacy.get("output_mode") == "structured_latest" else {}
    if payload and payload.get("schema_version") != 1:
        raise ValueError("unsupported daily technical snapshot schema")
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
    if rule.get("type") in {"PRICE", "PRICE_RANGE"}:
        # Temporary fail-closed boundary: historical definitions may contain
        # unstructured operating prerequisites in their price prose.  Price
        # remains visible as an Evaluation signal but cannot alone grant
        # Checklist eligibility until the compound definition is explicit.
        return rule.get("checklist_eligibility") == "price_only_explicit"
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
    # A prior weakening result covers only its own evidence, not a later event.
    covered_event = (
        compact((drift_scan or {}).get("status")).lower() == "current"
        and compact((drift_scan or {}).get("result")).lower() in {"improved", "unchanged", "weakened"}
    )
    if lifecycle != "EXITED" and event_state in {"important", "critical"} and event.get("thesis_relevant") and not covered_event:
        return "run_drift"
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
    if any(rule_can_promote_pre_buy(rule) for rule in rules):
        return "run_checklist"
    if any(rule.get("status") == "near_trigger" for rule in rules if rule.get("type") in {"PRICE", "PRICE_RANGE"}):
        return "price_near_trigger"
    if any(rule.get("status") == "near_trigger" for rule in rules):
        return "condition_near_trigger"
    return "keep_watch"


def _guidance_rule(
    rules: list[dict[str, Any]],
    *,
    statuses: set[str] | None = None,
    reasons: set[str] | None = None,
    scope: str | None = None,
) -> dict[str, Any] | None:
    """Return the first active Rule matching a deterministic guidance gate."""
    for rule in rules:
        if rule.get("active", True) is False:
            continue
        evaluation = rule.get("evaluation") or {}
        status = compact(rule.get("status") or evaluation.get("result")).lower()
        reason = compact(evaluation.get("reason")).lower()
        if statuses is not None and status not in statuses:
            continue
        if reasons is not None and reason not in reasons:
            continue
        if scope is not None and compact(rule.get("rule_scope")).lower() != scope:
            continue
        return rule
    return None


def canonical_skill_names() -> set[str]:
    """Return the canonical workflow names exposed by ``skills/*.md``."""
    if not CANONICAL_SKILLS_DIRECTORY.is_dir():
        return set()
    return {path.stem for path in CANONICAL_SKILLS_DIRECTORY.glob("*.md") if path.is_file()}


def thesis_drift_eligibility(
    lifecycle: str,
    rules: list[dict[str, Any]],
    event: dict[str, Any],
    drift_scan: dict[str, Any] | None,
    next_action: str,
) -> tuple[bool, str]:
    """Return the single deterministic gate for recommending thesis-drift."""
    scan_status = compact((drift_scan or {}).get("status")).lower()
    scan_result = compact((drift_scan or {}).get("result")).lower()
    formal_review_covers_current_trigger = (
        scan_status == "current"
        and scan_result in {"improved", "unchanged", "weakened"}
    )
    if next_action == "drift_recheck":
        return True, "current_formal_review_requires_additional_evidence"
    non_price_redline = _guidance_rule(rules, statuses={"triggered"}, scope="redline")
    if non_price_redline is not None and non_price_redline.get("type") not in {"PRICE", "PRICE_RANGE"}:
        if formal_review_covers_current_trigger:
            return False, "confirmed_redline_already_covered_by_current_formal_review"
        return True, "confirmed_non_price_redline_not_covered_by_current_formal_review"
    material_holding_event = (
        lifecycle == "HOLDING"
        and compact(event.get("state")).lower() in {"important", "critical"}
        and bool(event.get("thesis_relevant"))
    )
    if material_holding_event:
        if formal_review_covers_current_trigger:
            return False, "holding_event_already_covered_by_current_formal_review"
        return True, "holding_material_event_not_covered_by_current_formal_review"
    if next_action == "run_drift":
        if formal_review_covers_current_trigger:
            return False, "current_formal_review_already_covers_trigger"
        return True, "explicit_run_drift_action_not_covered_by_current_formal_review"
    return False, "no_current_thesis_drift_trigger"


def derive_review_coverage(
    decision: dict[str, Any],
    drift: dict[str, Any],
    drift_scan: dict[str, Any] | None,
    checklist: dict[str, Any],
    condition_review: dict[str, Any] | None,
    report_hash: str | None,
    generated_at: str,
) -> dict[str, Any]:
    """Project whether existing reviews still cover the current baseline."""
    manual = decision.get("manual_execution_review") or {}
    snapshot_hash = compact(
        (((manual.get("source_snapshot") or {}).get("main_report") or {}).get("sha256"))
    )
    reviewed_at = _parse_iso_datetime(manual.get("reviewed_at"))
    drift_checked_at = _parse_iso_datetime(drift.get("last_checked"))
    reviewed_drift_fingerprint = compact((drift_scan or {}).get("trigger_fingerprint"))
    formal_drift_fingerprint = compact((drift_scan or {}).get("current_trigger_fingerprint"))
    if not formal_drift_fingerprint and (drift_scan or {}).get("status") != "stale":
        formal_drift_fingerprint = reviewed_drift_fingerprint
    resolved_drift_fingerprint = compact(
        manual.get("resolved_drift_trigger_fingerprint")
    )
    generated_datetime = _parse_iso_datetime(generated_at)
    valid_until_text = compact(manual.get("valid_until"))
    try:
        valid_until = date.fromisoformat(valid_until_text) if valid_until_text else None
    except ValueError:
        valid_until = None
    manual_ready = (
        compact(manual.get("status")).lower() == "ready"
        and compact(manual.get("validity_state")).lower() == "ready"
        and bool(report_hash)
        and snapshot_hash == report_hash
        and (
            not manual.get("source_fingerprint_sha256")
            or manual.get("source_fingerprint_sha256")
            == manual.get("current_source_fingerprint_sha256")
        )
        and valid_until is not None
        and generated_datetime is not None
        and valid_until >= generated_datetime.astimezone(SHANGHAI_TIMEZONE).date()
    )
    if not manual:
        manual_status = "missing"
    elif snapshot_hash != report_hash:
        manual_status = "baseline_mismatch"
    elif valid_until is None or (
        generated_datetime is not None
        and valid_until < generated_datetime.astimezone(SHANGHAI_TIMEZONE).date()
    ):
        manual_status = "expired"
    elif not manual_ready:
        manual_status = "invalid"
    else:
        manual_status = "current"
    drift_resolution = "not_required"
    if drift_checked_at is not None:
        if manual_ready and reviewed_at is not None and reviewed_at < drift_checked_at:
            drift_resolution = "manual_review_precedes_drift"
        elif not manual_ready or reviewed_at is None:
            drift_resolution = "unresolved"
        elif not formal_drift_fingerprint or not resolved_drift_fingerprint:
            drift_resolution = "manual_review_missing_drift_binding"
        elif resolved_drift_fingerprint != formal_drift_fingerprint:
            drift_resolution = "manual_review_drift_binding_mismatch"
        elif (drift_scan or {}).get("status") == "stale":
            drift_resolution = "formal_review_no_longer_covers_current_trigger"
        else:
            drift_resolution = "resolved_by_current_manual_review"
    checklist_status = compact(checklist.get("status")).upper() or "UNKNOWN"
    checklist_review = (
        "completed"
        if checklist_status in {"PASS", "CONDITIONAL_PASS", "FAIL"}
        and bool(checklist.get("checked_at") or checklist.get("report_path"))
        else "missing"
    )
    condition_freshness = (
        compact((condition_review or {}).get("freshness")).lower() or "missing"
    )
    return {
        "formal_drift": {
            "reviewed_trigger_fingerprint": reviewed_drift_fingerprint or None,
            "current_trigger_fingerprint": formal_drift_fingerprint or None,
            "status": compact((drift_scan or {}).get("status")).lower() or "missing",
            "result": compact((drift_scan or {}).get("result")).lower() or None,
            "last_checked": drift.get("last_checked"),
        },
        "manual_decision": {
            "status": manual_status,
            "reviewed_at": manual.get("reviewed_at"),
            "valid_until": manual.get("valid_until"),
            "execution_key": manual.get("execution_key"),
            "resolved_drift_trigger_fingerprint": resolved_drift_fingerprint or None,
            "current_formal_drift_trigger_fingerprint": formal_drift_fingerprint or None,
            "drift_resolution": drift_resolution,
        },
        "checklist": {
            "status": checklist_status,
            "coverage": checklist_review,
            "checked_at": checklist.get("checked_at"),
            "report_path": checklist.get("report_path"),
        },
        "financial_condition_review": {
            "status": condition_freshness,
            "reviewed_at": (condition_review or {}).get("reviewed_at"),
            "last_probe_at": (condition_review or {}).get("last_probe_at"),
        },
    }


def derive_action_guidance(
    lifecycle: str,
    rules: list[dict[str, Any]],
    checklist: dict[str, Any],
    drift: dict[str, Any],
    event: dict[str, Any],
    tracking: dict[str, Any] | None,
    drift_scan: dict[str, Any] | None,
    next_action: str,
    review_coverage: dict[str, Any] | None = None,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Derive one user-facing blocker and route without changing control state.

    This is a navigation projection. It never promotes lifecycle, executes a
    Skill, or rewrites a Rule/Checklist/Drift result. Unknown observations are
    therefore not automatically turned into user work.
    """
    result = {
        "blocker_code": "none",
        "blocker_text": "当前没有需要人工处理的明确卡点",
        "next_action_code": "continue_monitoring",
        "next_action_text": "无需操作，系统继续观察",
        "recommended_skill": [],
        "recommended_skill_reason": "当前没有达到需要专业检查的确定性条件",
        "priority": "none",
        "requires_user_action": False,
        "completion_target": "等待新证据、条件变化或既定复核时间",
    }
    drift_eligible, drift_eligibility_reason = thesis_drift_eligibility(
        lifecycle, rules, event, drift_scan, next_action
    )
    review_coverage = review_coverage or {}

    def guidance(
        blocker_code: str,
        blocker_text: str,
        action_code: str,
        action_text: str,
        skills: list[str],
        skill_reason: str,
        priority: str,
        requires_user_action: bool,
        completion_target: str,
    ) -> dict[str, Any]:
        return {
            "blocker_code": blocker_code,
            "blocker_text": blocker_text,
            "next_action_code": action_code,
            "next_action_text": action_text,
            "recommended_skill": skills,
            "recommended_skill_reason": skill_reason,
            "priority": priority,
            "requires_user_action": requires_user_action,
            "completion_target": completion_target,
        }

    # Resolve uncovered material events before historical weakening or price
    # redlines can turn this into ordinary monitoring.
    if lifecycle != "EXITED" and next_action == "run_drift" and drift_eligible and compact(event.get("state")).lower() in {"important", "critical"} and event.get("thesis_relevant"):
        return guidance(
            "holding_material_event" if lifecycle == "HOLDING" else "thesis_review_required",
            "新的重要事件尚未被当前正式投资逻辑复核覆盖",
            "review_investment_thesis", "复核新事件对投资逻辑的影响",
            ["thesis-drift"], "旧复核与旧人工处置不能覆盖新事实",
            "urgent" if lifecycle == "HOLDING" else "normal", True,
            "复核当前事件并记录结果及其覆盖的证据",
        )
    redline = _guidance_rule(rules, statuses={"triggered"}, scope="redline")
    if redline is not None:
        condition = compact(redline.get("condition")) or "失效条件"
        if redline.get("type") in {"PRICE", "PRICE_RANGE"}:
            if lifecycle == "HOLDING":
                return guidance(
                    "holding_price_redline",
                    f"持仓价格相关红线已触发：{condition}",
                    "review_portfolio_position",
                    "结合估值与组合情况作人工判断",
                    ["portfolio-review"],
                    "价格或估值红线不是投资逻辑漂移，持仓动作应在组合层判断",
                    "urgent",
                    True,
                    "记录继续持有、调整仓位或退出的组合决策",
                )
            return guidance(
                "watch_price_redline",
                f"当前价格不符合观察标的的估值或安全边际要求：{condition}",
                "continue_monitoring",
                "无需研究，继续等待价格条件改善",
                [],
                "价格红线不等于投资逻辑变化，不应启动 thesis-drift",
                "monitor",
                False,
                "等待价格回到可研究区间，或由新的基本面事实改变估值依据",
            )
        holding_prefix = "持仓" if lifecycle == "HOLDING" else "观察标的"
        if not drift_eligible:
            return guidance(
                "covered_redline_requires_decision",
                f"当前正式投资逻辑复核已覆盖该失效条件：{condition}",
                "decide_research_disposition",
                "根据已有复核结论决定降级、继续观察或退出",
                [],
                "该触发已被当前有效的正式复核覆盖，不应重复运行 thesis-drift",
                "urgent" if lifecycle == "HOLDING" else "normal",
                True,
                "记录对既有复核结论的处置决定",
            )
        return guidance(
            "confirmed_redline",
            f"{holding_prefix}的失效条件已确认触发：{condition}",
            "review_investment_thesis",
            "复核投资逻辑并决定降级、继续观察或调整持仓",
            ["thesis-drift"],
            "当前已有确定性失效信号，需要核对其是否改变核心投资逻辑",
            "urgent" if lifecycle == "HOLDING" else "normal",
            True,
            "形成对该失效条件的明确处理结论，并记录继续、降级或退出依据",
        )

    event_state = compact(event.get("state")).lower()
    if lifecycle == "HOLDING":
        if drift.get("direction") == "weakened" and drift.get("severity") == "major":
            return guidance(
                "holding_thesis_weakened",
                "持仓公司的正式投资逻辑复核显示重大走弱",
                "review_holding_thesis",
                "围绕原始买入逻辑复核持仓",
                ["thesis-tracker"],
                "这是买入后的持续纪律问题，应以 Original Buy Thesis 为基准处理",
                "urgent",
                True,
                "明确继续持有、降低仓位或退出的依据，不覆盖 Original Buy Thesis",
            )
        if event_state in {"important", "critical"} and event.get("thesis_relevant"):
            if not drift_eligible:
                return guidance(
                    "covered_holding_event_requires_decision",
                    "当前正式投资逻辑复核已覆盖该持仓重要事件",
                    "decide_holding_disposition",
                    "阅读现有复核结论并决定持仓动作",
                    [],
                    "该事件已被当前有效的正式复核覆盖，不应重复运行 thesis-drift",
                    "urgent",
                    True,
                    "记录继续持有、调整仓位或退出的人工决定",
                )
            return guidance(
                "holding_material_event",
                "持仓公司出现已确认可能影响投资逻辑的重要事件",
                "review_holding_thesis",
                "复核事件对原始买入逻辑的影响",
                ["thesis-drift"],
                "事实已被事件层判定为重要且与投资逻辑相关，需要正式复核",
                "urgent",
                True,
                "确认 Original Buy Thesis 是否仍成立，并记录持仓动作",
            )
        alerts = [item for item in list((tracking or {}).get("alerts") or []) if isinstance(item, dict)]
        review_alerts = [
            item
            for item in alerts
            if item.get("kind") in {"review_due", "thesis_review"}
            or (
                not compact(item.get("kind"))
                and any(
                    token in compact(item.get("detail"))
                    for token in ("复核", "review", "季度")
                )
            )
        ]
        next_review = compact((tracking or {}).get("next_review_date"))
        as_of_datetime = _parse_iso_datetime(evaluated_at) or datetime.now().astimezone()
        review_overdue = False
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", next_review):
            try:
                review_overdue = date.fromisoformat(next_review) <= as_of_datetime.date()
            except ValueError:
                review_overdue = False
        if review_alerts or review_overdue:
            detail = compact((review_alerts[0] or {}).get("detail")) if review_alerts else f"复核日期 {next_review}（到期或逾期）"
            return guidance(
                "holding_review_due",
                detail,
                "review_holding_cycle",
                "核对持仓周期与最新事实",
                ["thesis-tracker"],
                "当前缺的是买入后的持续跟踪结论，不是新的买入前检查",
                "urgent",
                True,
                "完成本次持仓复核并更新下一次复核日期",
            )
        price_alerts = [item for item in alerts if item.get("kind") == "price_move"]
        if price_alerts:
            detail = compact(price_alerts[0].get("detail")) or "持仓出现价格异动"
            return guidance(
                "holding_price_move_unexplained",
                detail,
                "explain_holding_price_move",
                "核对价格异动是否来自公司、行业或市场事件",
                ["news-pulse"],
                "价格异动需要先归因；只有确认影响原始买入逻辑后才进入正式复核",
                "normal",
                True,
                "形成事件归因，并明确是否需要 thesis-drift 或继续观察",
            )
        return result

    if lifecycle == "EXITED":
        return {**result, "blocker_text": "该公司已退出当前投资流程", "completion_target": "无需后续动作"}

    if next_action in {"drop_or_recheck", "reduce_review"} and drift.get("direction") == "weakened":
        if drift.get("severity") == "minor":
            return guidance(
                "minor_thesis_weakening_monitored",
                "正式复核记录为轻度走弱，但未达到需要立即处置的程度",
                "continue_monitoring",
                "无需操作，按既定条件继续观察",
                [],
                "轻度走弱已被正式复核记录，不应每天重复生成研究或处置任务",
                "monitor",
                False,
                "等待下一份正式披露、条件变化或既定复核时点",
            )
        drift_resolution = compact(
            ((review_coverage.get("manual_decision") or {}).get("drift_resolution"))
        ).lower()
        if drift_resolution == "resolved_by_current_manual_review":
            return guidance(
                "major_weakening_decision_recorded",
                "重大走弱已有更新后的人工处置结论覆盖",
                "continue_monitoring",
                "无需重复处理，按已记录决定继续",
                [],
                "人工执行复核晚于正式 Drift 且当前仍有效，当前事项已经完成",
                "none",
                False,
                "仅在新证据、基线变化或复核到期时重新打开",
            )
        return guidance(
            "reviewed_thesis_weakened",
            "正式投资逻辑复核已经完成，并记录为走弱",
            "decide_research_disposition",
            "根据已有复核结论决定降级、继续观察或退出",
            [],
            "正式复核已有结果，不应重复运行 thesis-drift；当前缺的是投资者处置决定",
            "urgent" if lifecycle == "HOLDING" else "normal",
            True,
            "记录对现有走弱结论的处置决定，避免同一结果重复生成研究任务",
        )

    if next_action in {"run_drift", "drift_recheck"} and drift_eligible:
        if event_state in {"important", "critical"} and event.get("thesis_relevant"):
            blocker = "已确认的重要事件可能改变核心投资逻辑"
        elif drift.get("direction") == "weakened":
            blocker = "正式投资逻辑复核显示原有判断走弱"
        else:
            blocker = "现有证据要求重新核对核心投资逻辑"
        return guidance(
            "thesis_review_required",
            blocker,
            "review_investment_thesis",
            "复核投资逻辑",
            ["thesis-drift"],
            "当前问题已经超出普通事实核验，可能影响核心投资逻辑",
            "normal",
            True,
            "确认投资逻辑是否维持、改善、走弱或失效，并记录后续动作",
        )

    if next_action in {"run_drift", "drift_recheck"}:
        return guidance(
            "formal_review_already_current",
            "当前正式投资逻辑复核已覆盖这次触发",
            "decide_research_disposition",
            "阅读现有复核结论并决定后续状态",
            [],
            f"无需重复运行 thesis-drift：{drift_eligibility_reason}",
            "normal",
            True,
            "记录对当前正式复核结果的处置决定",
        )

    if next_action in {"drop_or_recheck", "reduce_review"}:
        return guidance(
            "review_result_requires_decision",
            "已有检查结果要求作出降级或重新评估决定",
            "decide_research_disposition",
            "阅读已有检查依据并决定后续状态",
            [],
            "当前缺的是对既有结果的人工决定，不应自动重复运行研究 Skill",
            "normal",
            True,
            "记录继续观察、降级或退出决定，并关闭同一结果产生的重复提醒",
        )

    checklist_status = compact(checklist.get("status")).upper()
    if lifecycle == "PRE_BUY" and checklist_status in {"PASS", "CONDITIONAL_PASS"}:
        return guidance(
            "human_purchase_decision",
            "买入前检查已有结果，当前等待投资者本人决策",
            "make_purchase_decision",
            "阅读检查结论并作出是否买入的人工判断",
            [],
            "专业检查已经完成，不需要重复运行 Skill",
            "normal",
            True,
            "记录买入、继续等待或放弃的决定；系统不得自动买入",
        )
    if lifecycle == "PRE_BUY" or next_action == "run_checklist":
        return guidance(
            "pre_buy_checklist_missing",
            "已具备买入推进资格，但正式买入前检查尚未完成",
            "run_investment_checklist",
            "执行买入前检查",
            ["investment-checklist"],
            "核心研究和买入推进资格已经具备，当前缺少正式买入决策审查",
            "normal",
            True,
            "生成可审计的 PASS、CONDITIONAL_PASS 或 FAIL 检查结论",
        )

    if checklist_status == "FAIL" and (
        ((review_coverage.get("checklist") or {}).get("coverage")) == "completed"
    ):
        return guidance(
            "checklist_failed_current",
            "已有买入前检查未通过，当前不具备买入资格",
            "continue_monitoring",
            "无需重复检查，继续观察或放弃",
            [],
            "Checklist 已有 FAIL 结果；没有新的重新开启条件时不应重复生成",
            "none",
            False,
            "仅在 Main Report、关键证据或明确买入资格发生变化时重新打开",
        )

    stale_review = _guidance_rule(rules, reasons={"stale_human_review", "ambiguous_review_mapping"})
    if stale_review is not None:
        condition = compact(stale_review.get("condition")) or "非价格条件"
        is_metric = stale_review.get("type") == "METRIC"
        return guidance(
            "condition_review_stale",
            f"已有人工条件结论无法覆盖当前证据：{condition}",
            "verify_condition_evidence",
            "重新核验该条件的最新事实",
            ["financial-data" if is_metric else "news-pulse"],
            "当前缺的是条件事实更新，不应直接启动完整投资逻辑漂移复核",
            "normal",
            True,
            "取得带日期和来源的当前事实，使条件恢复为可判定状态",
        )

    quote_error = _guidance_rule(
        rules,
        reasons={
            "quote_missing", "quote_missing_from_latest_refresh", "market_refresh_failed",
            "quote_date_missing", "historical_close_during_trading_session",
            "quote_timestamp_missing", "quote_timestamp_in_future",
            "quote_stale_during_trading_session",
        },
    )
    if quote_error is not None:
        return guidance(
            "market_data_unavailable",
            "当前缺少可信行情，价格条件不能判定",
            "wait_for_market_data",
            "无需投资者处理，等待行情链路恢复",
            [],
            "这是运行数据问题，不应转嫁为投资研究任务",
            "monitor",
            False,
            "行情恢复后由系统自动重新计算价格条件",
        )

    financial_error = _guidance_rule(
        rules,
        reasons={
            "financial_fact_missing", "financial_fact_conflict",
            "financial_fact_unit_mismatch", "financial_fact_invalid", "financial_fact_stale",
        },
    )
    if financial_error is not None:
        return guidance(
            "financial_data_unavailable",
            f"结构化财务事实暂不可用：{compact(financial_error.get('condition')) or '财务指标条件'}",
            "repair_financial_fact",
            "等待财务事实包补齐或修复",
            [],
            "规则定义已经明确，但事实缺失、过期或冲突属于数据链路问题",
            "monitor",
            False,
            "补齐同期间、同单位且带稳定证据引用的财务事实后自动重算",
        )

    if _guidance_rule(rules, statuses={"near_trigger"}) is not None:
        return guidance(
            "condition_near_trigger",
            "价格或其他条件接近触发，但尚未形成完整推进资格",
            "continue_monitoring",
            "无需操作，继续观察",
            [],
            "接近条件只是自动观察信号，不等于买入前检查任务",
            "monitor",
            False,
            "等待条件明确满足，或出现需要核验的新事实",
        )

    missing_metric = _guidance_rule(rules, reasons={"missing_computable_definition"})
    if missing_metric is not None:
        return guidance(
            "financial_definition_missing",
            f"经营条件尚无可计算定义：{compact(missing_metric.get('condition')) or '经营指标条件'}",
            "continue_monitoring",
            "当前无需操作；进入重点研究时再补齐财务定义",
            [],
            "这是规则定义缺口；financial-data 只能提供事实，不能替用户批准指标、阈值或运算符",
            "monitor",
            False,
            "由人工批准 metric、operator、threshold、period、unit 后，再由 financial-data 提供事实包",
        )

    awaiting = _guidance_rule(
        rules,
        reasons={"awaiting_scheduled_evidence", "awaiting_event_confirmation", "reviewed_evidence_insufficient"},
    )
    if awaiting is not None:
        return guidance(
            "evidence_not_available",
            "相关条件仍在等待披露、事件确认或充分证据",
            "continue_monitoring",
            "无需操作，等待新证据",
            [],
            "当前没有足够事实支持专业检查，unknown 不应自动成为人工待办",
            "monitor",
            False,
            "新证据到达后由系统重新判断是否需要专业 Skill",
        )
    return result


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


def classify_drift_audit_review(
    lifecycle: str,
    drift_scan: dict[str, Any] | None,
    drift: dict[str, Any],
    canonical_report_sha256: str | None,
    rules: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Classify the tracked Drift audit from research authority only.

    ``drift_scan`` on Company State is a runtime projection: its derived
    ``status`` and ``current_trigger_fingerprint`` may change with quotes or
    Event Radar.  The tracked audit must not inherit those changes.  For this
    projection a persisted checkpoint remains current while it still covers
    the same canonical report, mode, and fingerprint contract.  A changed
    report (or incompatible checkpoint contract) is stable Git evidence that
    a new Drift review is required.

    The generic Company State ``next_action`` is intentionally not an input.
    Formal Drift direction is used only for the stable research disposition,
    never to reproduce quote/event-driven dashboard actions.
    """
    scan = drift_scan if isinstance(drift_scan, dict) else {}
    has_checkpoint = any(
        scan.get(field) is not None
        for field in ("checked_at", "batch_id", "source")
    )
    if not has_checkpoint:
        checkpoint_status = "missing"
    elif (
        compact(scan.get("mode")).lower() != "watch"
        or scan.get("trigger_fingerprint_version") != drift_scan_state.FINGERPRINT_VERSION
        or scan.get("baseline_report_sha256") != canonical_report_sha256
    ):
        checkpoint_status = "stale"
    else:
        checkpoint_status = "current"

    checkpoint_result = compact(scan.get("result")).lower() or None
    stable_redlines = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("active", True) is not False
        and rule.get("status") == "triggered"
        and compact(rule.get("rule_scope")).lower() == "redline"
        and rule.get("type") not in {"PRICE", "PRICE_RANGE"}
    ]
    stable_redline_requests_drift = any(
        compact(rule.get("action")).lower() == "run_drift"
        for rule in stable_redlines
    )
    if lifecycle != "WATCH":
        category = "not_applicable"
        current_action = "not_applicable"
    elif checkpoint_status == "stale" or stable_redline_requests_drift:
        category = "true_current_drift"
        current_action = "run_drift"
    elif checkpoint_status == "current" and checkpoint_result == "unknown":
        category = "reviewed_insufficient_evidence"
        current_action = "run_drift"
    elif checkpoint_status == "current":
        category = "reviewed_current"
        current_action = (
            "drop_or_recheck"
            if stable_redlines or compact(drift.get("direction")).lower() == "weakened"
            else "keep_watch"
        )
    elif drift.get("last_checked"):
        category = "reviewed_not_recognized"
        current_action = "reviewed_waiting_disposition"
    else:
        category = "never_reviewed"
        current_action = "keep_watch"

    return {
        "category": category,
        "label": DRIFT_REVIEW_LABELS[category],
        "current_action": current_action,
        "checkpoint_status": checkpoint_status,
        "checkpoint_result": checkpoint_result,
        "last_checked": drift.get("last_checked"),
    }


def build_drift_review_audit(state_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic research-only Drift audit."""
    companies = [
        item
        for item in state_payload.get("companies", [])
        if isinstance(item, dict) and item.get("lifecycle") in {"WATCH", "PRE_BUY"}
    ]
    rows: list[dict[str, Any]] = []
    counts = {category: 0 for category in DRIFT_REVIEW_CATEGORIES}
    for item in companies:
        review = classify_drift_audit_review(
            str(item.get("lifecycle") or ""),
            item.get("drift_scan"),
            item.get("drift") or {},
            item.get("canonical_report_sha256"),
            ((item.get("decision_rules") or {}).get("rules") or []),
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
                "current_action": review.get("current_action"),
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
    main_report_review_payload: dict[str, Any] | None = None,
    investment_disposition_payload: dict[str, Any] | None = None,
    legacy_mode: bool = False,
) -> dict[str, Any]:
    """Evaluate persisted rules; only an explicit legacy mode may infer them."""
    data_directory = repo_root / "data" / "investment-dashboard"
    generated_at = generated_at or now_iso()
    quotes = _quote_by_ticker(data_directory)
    sentiment = _sentiment_by_ticker(data_directory)
    overrides = _load_overrides(data_directory)
    drift_values = _load_drift(data_directory)
    condition_reviews = _load_condition_reviews(
        data_directory,
        current_review_payload=main_report_review_payload,
    )
    financial_fact_payload = financial_facts.load(
        data_directory / financial_facts.RELATIVE_PATH.name,
        strict=not legacy_mode,
    )
    light_thesis_payload = light_thesis_signals.load(
        data_directory / light_thesis_signals.RELATIVE_PATH.name,
        strict=True,
    )
    light_thesis_records = light_thesis_payload.get("companies") or {}
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
    evaluation_companies: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    technical_latest: list[dict[str, Any]] = []
    checklist_states: list[dict[str, Any]] = []
    light_thesis_projections: list[dict[str, Any]] = []
    for decision in decisions:
        ticker = compact(decision.get("ticker")).upper()
        cid = company_id(decision)
        attached_tracking = decision.get("post_buy_tracking")
        tracking_record = (
            attached_tracking
            if isinstance(attached_tracking, dict)
            and compact(attached_tracking.get("status")) != "not_tracked"
            else tracking.get(ticker)
        )
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
        report_hash = canonical_report_hash(decision, repo_root)
        company_condition_review = condition_reviews.get(ticker)
        company_financial_facts = financial_facts.for_ticker(financial_fact_payload, ticker)
        condition_resolver = lambda candidate: _condition_review_for_rule(
            company_condition_review, candidate, report_hash
        )
        fact_resolver = lambda candidate: financial_facts.resolve(
            company_financial_facts,
            candidate,
            baseline_report_sha256=report_hash,
        )
        company_evaluations: list[dict[str, Any]] = []
        for rule in rules:
            event_triggered = bool(event.get("thesis_relevant")) and event.get("state") in {"important", "critical"}
            evaluation = evaluate_rule_result(
                rule,
                quote,
                event_triggered,
                event,
                condition_resolver(rule),
                evaluated_at=generated_at,
                financial_fact=fact_resolver(rule),
                condition_review_resolver=condition_resolver,
                financial_fact_resolver=fact_resolver,
            )
            rule["status"] = evaluation["result"]
            rule["last_checked"] = generated_at
            rule["evaluation"] = evaluation
            company_evaluations.append(evaluation)
        checklist = _checklist_state(decision)
        drift_raw = drift_values.get(ticker) or drift_values.get(cid) or {}
        drift = {
            "mode": "holding" if compact((tracking_record or {}).get("status")).lower() in {"holding", "paused", "closed"} else "watch",
            "direction": _drift_value(drift_raw.get("direction"), "unknown"),
            "severity": _drift_value(drift_raw.get("severity"), "none"),
            "last_checked": drift_raw.get("last_checked"),
            "next_review": drift_raw.get("next_review"),
            "summary": drift_raw.get("summary"),
            "source": drift_raw.get("source"),
        }
        lifecycle, warning = _lifecycle((overrides.get(ticker) or {}).get("lifecycle"), tracking_record, rules, checklist)
        light_thesis = light_thesis_signals.project_record(
            light_thesis_records.get(ticker),
            lifecycle=lifecycle,
            canonical_report_path=decision.get("report_path") or None,
            canonical_report_sha256=report_hash,
        )
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
            lifecycle, rules, checklist, drift, event, tracking_record, drift_scan
        )
        review_coverage = derive_review_coverage(
            decision,
            drift,
            drift_scan,
            checklist,
            company_condition_review,
            report_hash,
            generated_at,
        )
        action_guidance = derive_action_guidance(
            lifecycle,
            rules,
            checklist,
            drift,
            event,
            tracking_record,
            drift_scan,
            next_action,
            review_coverage,
            evaluated_at=generated_at,
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
            "light_thesis_signal": light_thesis,
            "review_coverage": review_coverage,
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
            "action_guidance": action_guidance,
            "needs_attention": next_action not in {"keep_watch", "hold", "none"} or lifecycle == "PRE_BUY",
            "warning": warning,
            "post_buy_tracking": tracking_record if tracking_record else {"status": "not_tracked"},
            "generated_at": generated_at,
        }
        state = investment_dispositions.project_company(
            state, investment_disposition_payload
        )
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
        evaluation_companies.append({
            "company_id": cid,
            "company": decision.get("company"),
            "ticker": ticker or None,
            "market": decision.get("market") or "unknown",
            "evaluations": company_evaluations,
        })
        technical_latest.append({"company_id": cid, "company": decision.get("company"), "ticker": ticker or None, "market": decision.get("market"), **technical})
        checklist_states.append({"company_id": cid, "company": decision.get("company"), "ticker": ticker or None, "market": decision.get("market"), **checklist})
        light_thesis_projections.append({
            "company_id": cid,
            "company": decision.get("company"),
            "ticker": ticker or None,
            "market": decision.get("market"),
            **light_thesis,
        })

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
    evaluations_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "company_count": len(evaluation_companies),
        "evaluation_count": sum(len(item["evaluations"]) for item in evaluation_companies),
        "companies": evaluation_companies,
    }
    light_thesis_projection_payload = {
        "schema_version": light_thesis_signals.SCHEMA_VERSION,
        "generated_at": generated_at,
        "authority": "git_source_read_only_projection",
        "company_count": len(light_thesis_projections),
        "companies": light_thesis_projections,
    }
    result = {
        "rules": rules_payload,
        "state": state_payload,
        "technical": technical_payload,
        "checklist": checklist_payload,
        "evaluations": evaluations_payload,
        "light_thesis": light_thesis_projection_payload,
        "drift_review_audit": build_drift_review_audit(state_payload),
    }
    if write:
        # Rule definitions are written only by extraction/lifecycle commands.
        # This build-time projection contains volatile statuses and timestamps.
        write_json(data_directory / STATE_RELATIVE.name, state_payload)
        write_json(data_directory / TECHNICAL_RELATIVE.name, technical_payload)
        write_json(data_directory / CHECKLIST_RELATIVE.name, checklist_payload)
        write_json(data_directory / EVALUATIONS_RELATIVE.name, evaluations_payload)
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
            decision["action_guidance"] = state.get("action_guidance")
            decision["manual_disposition"] = state.get("manual_disposition")


def validate_payloads(payloads: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rules = payloads.get("rules") or {}
    state = payloads.get("state") or {}
    evaluations = payloads.get("evaluations") or {}
    if rules.get("schema_version") != SCHEMA_VERSION:
        errors.append("decision_rules schema_version")
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append("company_state schema_version")
    if rules.get("rule_types") != list(RULE_TYPES):
        errors.append("decision_rules rule_types")
    if evaluations and evaluations.get("schema_version") != SCHEMA_VERSION:
        errors.append("rule_evaluations schema_version")
    evaluation_rows = [
        evaluation
        for company in evaluations.get("companies", [])
        if isinstance(company, dict)
        for evaluation in company.get("evaluations", [])
        if isinstance(evaluation, dict)
    ]
    if evaluations and evaluations.get("evaluation_count") != len(evaluation_rows):
        errors.append("rule_evaluations evaluation_count")
    for evaluation in evaluation_rows:
        if evaluation.get("result") not in RULE_STATUSES:
            errors.append(f"invalid evaluation result: {evaluation.get('rule_id')}")
    scan = payloads.get("drift_scan")
    if scan is not None:
        errors.extend(f"{error}" for error in drift_scan_state.validate_payload(scan))
    for item in state.get("companies", []):
        if item.get("lifecycle") not in LIFECYCLES:
            errors.append(f"invalid lifecycle: {item.get('ticker')}")
        guidance = item.get("action_guidance")
        if not isinstance(guidance, dict):
            errors.append(f"missing action guidance: {item.get('ticker')}")
        else:
            required_guidance_fields = {
                "blocker_code", "blocker_text", "next_action_code", "next_action_text",
                "recommended_skill", "recommended_skill_reason", "priority",
                "requires_user_action", "completion_target",
            }
            if not required_guidance_fields <= set(guidance):
                errors.append(f"incomplete action guidance: {item.get('ticker')}")
            if guidance.get("priority") not in GUIDANCE_PRIORITIES:
                errors.append(f"invalid action guidance priority: {item.get('ticker')}")
            if not isinstance(guidance.get("recommended_skill"), list):
                errors.append(f"invalid action guidance skills: {item.get('ticker')}")
            else:
                available_skills = canonical_skill_names()
                missing_skills = sorted(set(guidance.get("recommended_skill") or []) - available_skills)
                if missing_skills:
                    errors.append(
                        f"action guidance skill not available: {item.get('ticker')} ({','.join(missing_skills)})"
                    )
            if not isinstance(guidance.get("requires_user_action"), bool):
                errors.append(f"invalid action guidance user flag: {item.get('ticker')}")
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
