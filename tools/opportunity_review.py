#!/usr/bin/env python3
"""Model-led A-share opportunity scanning and on-demand deep review.

This module deliberately separates two decisions:

* Models identify whether a stock deserves the investor's attention now.
* The investor decides whether to buy, hold, or do nothing.

It never changes a report judgment, deterministic execution-state label, price
rule, technical indicator, sentiment score, or Checklist result.  Those are
inputs for semantic review rather than mechanical admission gates.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from source_hash import canonical_file_sha256
from deepseek_provider import DeepSeekConfigurationError, load_config as load_deepseek_config, usage_summary


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import decision_consistency_review as consistency  # noqa: E402
import report_judgment  # noqa: E402
from sentiment_snapshot import SentimentError, http_json, parse_json_block  # noqa: E402


MARKET = "A股"
SCAN_SCHEMA_VERSION = 3
DEEP_SCHEMA_VERSION = 1
OPPORTUNITY_PROMPT_CONTRACT_VERSION = 3
MATERIAL_TRIGGER_VERSION = 3
INCREMENTAL_CONTRACT_VERSION = 3
VERIFICATION_CONTRACT_VERSION = 1
MAX_REUSE_AGE_DAYS = 7

OPPORTUNITY_SCAN_USER_AGENT = "ai-berkshire-opportunity-review/1"
TRANSPORT_OPENAI_CHAT = "openai_chat"
TRANSPORT_ANTHROPIC_MESSAGES = "anthropic_messages"
TRANSPORT_OPENAI_RESPONSES = "openai_responses"


class OpportunityReviewError(RuntimeError):
    """Raised when an opportunity-review result is unusable."""


class OpportunityResponseParseError(OpportunityReviewError):
    """Keep malformed provider text available for one bounded repair request."""

    def __init__(self, message: str, *, raw_text: str, reasoning: dict[str, Any]):
        super().__init__(message)
        self.raw_text = raw_text
        self.reasoning = reasoning


def error_category(error: Exception) -> str:
    if isinstance(error, OpportunityResponseParseError):
        return "json_parse_error"
    text = str(error).casefold()
    if "no output text" in text or "no text block" in text or "no choices" in text or "no message" in text:
        return "empty_response"
    if isinstance(error, (TimeoutError, urllib.error.URLError, OSError)):
        return "transport_error"
    if "must include" in text or "must be" in text or "校验" in text:
        return "schema_validation_error"
    return "provider_error"


@dataclass(frozen=True)
class ModelDefaults:
    role: str
    model: str
    transport: str
    endpoint: str
    prefix: str


@dataclass(frozen=True)
class ModelConfig:
    role: str
    model: str
    transport: str
    endpoint: str
    api_key: str
    max_tokens: int
    timeout_seconds: int
    max_retries: int
    reasoning_effort: str
    thinking_budget_tokens: int


MODEL_DEFAULTS = {
    "opportunity_initial": ModelDefaults(
        role="opportunity_initial",
        model="deepseek-flash",
        transport=TRANSPORT_OPENAI_CHAT,
        endpoint="https://api.deepseek.com/chat/completions",
        prefix="OPPORTUNITY_SCAN_",
    ),
    "opportunity_verify": ModelDefaults(
        role="opportunity_verify",
        model="deepseek-flash",
        transport=TRANSPORT_OPENAI_CHAT,
        endpoint="https://api.deepseek.com/chat/completions",
        prefix="OPPORTUNITY_VERIFY_",
    ),
    "opportunity_deep": ModelDefaults(
        role="opportunity_deep",
        model="deepseek-flash",
        transport=TRANSPORT_OPENAI_CHAT,
        endpoint="https://api.deepseek.com/chat/completions",
        prefix="OPPORTUNITY_DEEP_",
    ),
}

OPPORTUNITY_STATES = {"当前机会", "临近机会", "暂不构成当前机会", "证据不足"}
LEGACY_STATE_ALIASES = {
    "机会": "当前机会",
    "条件机会": "临近机会",
    "暂不构成机会": "暂不构成当前机会",
}
CONFIDENCE = {"high", "medium", "low"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def clean_text(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def parse_integer(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        return default
    return min(maximum, max(minimum, parsed))


def model_config(role: str) -> ModelConfig:
    """Read one DeepSeek Official role without leaking its token to artifacts."""
    defaults = MODEL_DEFAULTS[role]
    report_judgment.load_model_environment()
    prefix = defaults.prefix
    timeout_default = 240 if role == "opportunity_initial" else 360
    default_effort = "high" if role == "opportunity_initial" else "max"
    default_max_tokens = 8192 if role == "opportunity_initial" else 12288
    try:
        shared = load_deepseek_config(
            role,
            prefix=prefix,
            default_effort=default_effort,
            default_max_tokens=default_max_tokens,
            default_timeout=timeout_default,
        )
    except DeepSeekConfigurationError as error:
        raise OpportunityReviewError(str(error)) from error
    assert shared is not None
    return ModelConfig(
        role=role,
        model=shared.model,
        transport=defaults.transport,
        endpoint=shared.endpoint,
        api_key=shared.api_key,
        max_tokens=shared.max_tokens,
        timeout_seconds=shared.timeout_seconds,
        max_retries=shared.max_retries,
        reasoning_effort=shared.reasoning_effort,
        thinking_budget_tokens=parse_integer(
            os.environ.get(f"{prefix}THINKING_BUDGET_TOKENS"), 32000, 1024, 48000
        ),
    )


def opportunity_scan_headers() -> dict[str, str]:
    """Return only generic, non-sensitive official-provider headers."""
    return {"User-Agent": OPPORTUNITY_SCAN_USER_AGENT}


def report_sha256(repo_root: Path, decision: dict[str, Any]) -> str:
    report_path = repo_root / str(decision.get("report_path") or "")
    if not report_path.is_file():
        raise OpportunityReviewError(f"main report does not exist: {decision.get('report_path')}")
    return canonical_file_sha256(report_path)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def load_board(repo_root: Path) -> dict[str, Any]:
    board_path = repo_root / "data" / "investment-dashboard" / "decision_board.json"
    board = load_json(board_path, {})
    if not isinstance(board.get("decisions"), list):
        raise OpportunityReviewError(f"invalid decision board: {board_path}")
    return board


def find_decisions(repo_root: Path, ticker: str | None = None) -> list[dict[str, Any]]:
    ticker_upper = str(ticker or "").upper().strip()
    decisions = [
        item
        for item in load_board(repo_root).get("decisions", [])
        if isinstance(item, dict)
        and item.get("market") == MARKET
        and item.get("report_path")
        and (not ticker_upper or str(item.get("ticker") or "").upper() == ticker_upper)
    ]
    if ticker_upper and not decisions:
        raise OpportunityReviewError(f"ticker not found among A-share decisions: {ticker_upper}")
    return sorted(decisions, key=lambda item: (str(item.get("company") or ""), str(item.get("ticker") or "")))


def snapshot_maps(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sentiment = load_json(repo_root / "site" / "data" / "sentiment.json", {"companies": []})
    intraday = load_json(
        repo_root / "data" / "investment-dashboard" / "intraday_technical.json", {"companies": []}
    )
    quotes = load_json(
        repo_root / "data" / "investment-dashboard" / "quotes" / "latest.json", {"quotes": []}
    )
    by_ticker = lambda rows: {
        str(item.get("ticker") or "").upper(): item
        for item in rows
        if isinstance(item, dict) and item.get("ticker")
    }
    sentiment_rows = by_ticker(sentiment.get("companies", []))
    market_layers = sentiment.get("market_sentiment") if isinstance(sentiment.get("market_sentiment"), dict) else {}
    for row in sentiment_rows.values():
        market = str(row.get("market") or "")
        row.setdefault("market_sentiment", market_layers.get(market))
    return (
        sentiment_rows,
        by_ticker(intraday.get("companies", [])),
        by_ticker(quotes.get("quotes", [])),
    )


def build_opportunity_input(
    decision: dict[str, Any],
    *,
    repo_root: Path,
    sentiment: dict[str, Any] | None,
    intraday: dict[str, Any] | None,
    quote: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the same auditable evidence set for each independent model.

    The deterministic price context is included as a fact, but this function
    never turns it into a gate.  That keeps report language and context in the
    model's semantic review rather than mechanically filtering a stock out.
    """
    facts = consistency.build_review_input(
        decision,
        repo_root=repo_root,
        sentiment=sentiment,
        intraday=intraday,
        quote=quote,
    )
    facts["review_contract"] = {
        "purpose": "识别当前是否已经出现值得投资者优先决策的正向机会，不是买卖指令",
        "current_panel_rule": "只有模型判为当前机会才进入主面板；临近机会单独折叠展示",
        "investor_role": "投资者根据完整材料自行决定买、不买或继续观察",
        "mechanical_gate_warning": "本地价格匹配、Checklist、技术面和情绪均是输入事实，不得机械地充当机会否决器",
        "risk_authority_boundary": "必须明确讨论当前已确认红线、投资逻辑复核要求与未解决条件。机会只是研究线索，不得覆盖确定性风险状态、授予Checklist资格或推导可以买入。缺失或冲突的当前状态不能当作风险已解除。",
    }
    facts["evidence_reference_catalog"] = evidence_reference_catalog(facts)
    encoded = json.dumps(facts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    facts["input_sha256"] = hashlib.sha256(encoded).hexdigest()
    return facts


def evidence_reference_catalog(facts: dict[str, Any]) -> dict[str, list[str]]:
    """Expose exact, typed locators that a model may cite without inventing IDs."""
    source_ids: set[str] = set()
    rule_ids: set[str] = set()
    report_paths: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and item.strip():
                    if key == "source_id":
                        source_ids.add(item.strip())
                    elif key == "rule_id":
                        rule_ids.add(item.strip())
                    elif key in {"report_path", "canonical_report", "source_report"}:
                        report_paths.add(item.strip())
                    elif key == "path" and item.strip().startswith("reports/"):
                        report_paths.add(item.strip())
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(facts)
    checklist = facts.get("checklist") if isinstance(facts.get("checklist"), dict) else {}
    gates = {
        clean_text(item.get("name"), 120)
        for item in checklist.get("gates", [])
        if isinstance(item, dict) and clean_text(item.get("name"), 120)
    }
    return {
        "source_ids": sorted(source_ids),
        "rule_ids": sorted(rule_ids),
        "checklist_gates": sorted(gates),
        "report_paths": sorted(report_paths),
    }


def stable_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def stable_price_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Return only deterministic price-rule semantics, never live prices."""
    return {
        "action_kind": rule.get("action_kind"),
        "min": rule.get("min"),
        "ceiling": rule.get("ceiling"),
        "requires_validation": bool(rule.get("requires_validation")),
        "validation_condition": clean_text(rule.get("validation_condition"), 240),
    }


def price_position_bucket(
    price: float | None,
    *,
    status: str,
    matched_rules: list[dict[str, Any]],
    all_rules: list[dict[str, Any]],
) -> str:
    """Coarsen price position for model-refresh decisions only.

    This is deliberately not an investment gate.  It merely prevents pennies
    of quote noise from causing a model call while still allowing a large move
    inside one broad rule to trigger a refresh.
    """
    if price is None:
        return "no_quote"
    bounded = [
        rule
        for rule in matched_rules
        if isinstance(rule.get("min"), (int, float))
        and isinstance(rule.get("ceiling"), (int, float))
        and float(rule["ceiling"]) > float(rule["min"])
    ]
    if bounded:
        rule = sorted(
            bounded,
            key=lambda item: (
                float(item["ceiling"]) - float(item["min"]),
                float(item["min"]),
                float(item["ceiling"]),
            ),
        )[0]
        position = (price - float(rule["min"])) / (float(rule["ceiling"]) - float(rule["min"]))
        if position <= 1 / 3:
            return "inside_low"
        if position <= 2 / 3:
            return "inside_mid"
        return "inside_high"

    if matched_rules:
        # One-sided entry rules use distance from their nearest boundary.
        ceilings = [float(rule["ceiling"]) for rule in matched_rules if isinstance(rule.get("ceiling"), (int, float))]
        floors = [float(rule["min"]) for rule in matched_rules if isinstance(rule.get("min"), (int, float))]
        boundary = min(ceilings, key=lambda value: abs(price - value)) if ceilings else (
            min(floors, key=lambda value: abs(price - value)) if floors else None
        )
        if boundary and boundary > 0:
            distance = abs(price - boundary) / boundary
            if distance <= 0.02:
                return "near_boundary"
            if distance <= 0.10:
                return "inside_mid"
        return "inside_low"

    ceilings = [float(rule["ceiling"]) for rule in all_rules if isinstance(rule.get("ceiling"), (int, float))]
    floors = [float(rule["min"]) for rule in all_rules if isinstance(rule.get("min"), (int, float))]
    if status == "above_all_entry_rules" and ceilings:
        distance = (price - max(ceilings)) / max(ceilings) if max(ceilings) > 0 else 1.0
        return "near_boundary" if distance <= 0.02 else "outside_near" if distance <= 0.10 else "above_all_rules"
    if floors and price < min(floors):
        distance = (min(floors) - price) / min(floors) if min(floors) > 0 else 1.0
        return "near_boundary" if distance <= 0.02 else "outside_near" if distance <= 0.10 else "below_all_rules"
    return "outside"


def price_materiality_signature(facts: dict[str, Any]) -> dict[str, Any]:
    context = facts.get("local_price_context") if isinstance(facts.get("local_price_context"), dict) else {}
    policy = facts.get("execution_policy") if isinstance(facts.get("execution_policy"), dict) else {}
    all_rules = [stable_price_rule(item) for item in policy.get("price_rules", []) if isinstance(item, dict)]
    matched = [stable_price_rule(item) for item in context.get("matched_rules", []) if isinstance(item, dict)]
    all_rules.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    matched.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    raw_price = context.get("price")
    price = float(raw_price) if isinstance(raw_price, (int, float)) and math.isfinite(float(raw_price)) else None
    return {
        "status": context.get("status", "missing_quote"),
        "matched_rule_identities": [stable_sha256(item) for item in matched],
        "matched_requires_validation": [item["requires_validation"] for item in matched],
        "rule_boundary_identity": stable_sha256(all_rules),
        "position_bucket": price_position_bucket(
            price,
            status=str(context.get("status") or ""),
            matched_rules=matched,
            all_rules=all_rules,
        ),
    }


def discrete_technical(value: Any, *, intraday: bool = False) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    result: dict[str, Any] = {
        "status": value.get("status", "missing"),
        "state": value.get("state", "待复核"),
    }
    if not intraday:
        result["valid_buy_candidate"] = value.get("valid_buy_candidate")
        result["lights"] = sorted(
            [
                {"dimension": item.get("dimension"), "light": item.get("light")}
                for item in value.get("lights", [])
                if isinstance(item, dict)
            ],
            key=lambda item: str(item.get("dimension") or ""),
        )
    else:
        # Only named categorical states are material. Raw OHLC/indicator values,
        # timestamps and free-form reasons intentionally stay out.
        discrete_keys = {
            "state", "status", "signal", "trend_state", "momentum_state",
            "volatility_state", "ma_alignment", "light", "direction",
        }
        for section in ("trend", "momentum", "volatility", "session"):
            source = value.get(section) if isinstance(value.get(section), dict) else {}
            selected = {
                key: item
                for key, item in source.items()
                if key in discrete_keys and isinstance(item, (str, bool, type(None)))
            }
            if selected:
                result[section] = selected
    return result


def sentiment_material_signature(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, dict) else {}
    combined = value.get("combined") if isinstance(value.get("combined"), dict) else {}
    news = value.get("news") if isinstance(value.get("news"), dict) else {}
    formal = news.get("formal_sentiment") if isinstance(news.get("formal_sentiment"), dict) else news
    examples = [
        {
            "title": clean_text(item.get("title"), 100),
            "published_at": item.get("published_at"),
            "event_type": item.get("event_type"),
            "direction": item.get("direction"),
            "impact": item.get("impact"),
            "source_tier": item.get("source_tier"),
        }
        for item in value.get("scored_news_examples", [])
        if isinstance(item, dict)
    ]
    examples.sort(key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return {
        "status": value.get("status", "missing"),
        "combined_state": combined.get("state"),
        "formal_news_state": formal.get("state"),
        "formal_news_confidence": formal.get("confidence"),
        "material_evidence_digest": stable_sha256(examples),
    }


def stable_current_facts(value: Any) -> Any:
    """Ignore refresh clocks, retaining evidence dates, identities and results."""
    volatile = {"generated_at", "projection_generated_at", "evaluated_at", "evaluation_at",
                "checked_at", "last_checked", "last_attempt_at", "elapsed_seconds"}
    if isinstance(value, dict):
        if value.get("type") in {"PRICE", "PRICE_RANGE"}:
            value = dict(value)
            evaluation = value.get("evaluation") or {}
            # Price movement is already represented by the bounded price
            # bucket; penny changes must not reopen an otherwise same task.
            value["evaluation"] = {key: evaluation.get(key) for key in ("result", "reason")}
        return {key: stable_current_facts(item) for key, item in value.items() if key not in volatile}
    if isinstance(value, list):
        return sorted((stable_current_facts(item) for item in value), key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return value


def material_trigger_snapshot(facts: dict[str, Any], report_hash: str) -> dict[str, Any]:
    primary = facts.get("primary_judgment") if isinstance(facts.get("primary_judgment"), dict) else {}
    policy = facts.get("execution_policy") if isinstance(facts.get("execution_policy"), dict) else {}
    checklist = facts.get("checklist") if isinstance(facts.get("checklist"), dict) else {}
    return {
        "version": MATERIAL_TRIGGER_VERSION,
        "report_sha256": report_hash,
        "current_decision_facts": stable_current_facts(facts.get("current_decision_facts")),
        "primary_judgment": {
            key: primary.get(key)
            for key in ("label", "action_kind", "empty_position_action", "trigger_condition", "summary", "artifact_status", "source_matches", "model_consensus")
        },
        "execution_policy": {
            "main_label": policy.get("main_label"),
            "condition_mode": policy.get("condition_mode"),
            "event_condition": policy.get("event_condition"),
            "guard_condition": policy.get("guard_condition"),
            "reliability": policy.get("reliability"),
            "price_rules": sorted(
                [stable_price_rule(item) for item in policy.get("price_rules", []) if isinstance(item, dict)],
                key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
            ),
        },
        "price": price_materiality_signature(facts),
        "checklist": {
            "status": checklist.get("status", "missing"),
            "hard_veto": checklist.get("hard_veto"),
            "hard_veto_label": checklist.get("hard_veto_label"),
            "mirror_test": checklist.get("mirror_test"),
            "confidence": checklist.get("confidence"),
            "summary": checklist.get("summary"),
            "gates": sorted(
                [
                    {"name": gate.get("name"), "result": gate.get("result")}
                    for gate in checklist.get("gates", [])
                    if isinstance(gate, dict)
                ],
                key=lambda item: str(item.get("name") or ""),
            ),
        },
        "daily_technical": discrete_technical(facts.get("daily_technical")),
        "sentiment": sentiment_material_signature(facts.get("sentiment")),
    }


def assessment_contract(config: ModelConfig) -> dict[str, Any]:
    return {
        "scan_schema_version": SCAN_SCHEMA_VERSION,
        "incremental_contract_version": INCREMENTAL_CONTRACT_VERSION,
        "opportunity_prompt_contract_version": OPPORTUNITY_PROMPT_CONTRACT_VERSION,
        "trigger_fingerprint_version": MATERIAL_TRIGGER_VERSION,
        "provider": "deepseek_official",
        "model": "deepseek-flash",
        "transport": config.transport,
        "initial_reasoning_effort": "high",
        "verification_reasoning_effort": "max",
        "verification_contract_version": VERIFICATION_CONTRACT_VERSION,
    }


def review_schema(deep: bool) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "opportunity_state": "仅可取：当前机会/临近机会/暂不构成当前机会/证据不足",
        "opportunity_summary": "不超过120字，解释当前机会强度；不是买卖指令",
        "why_now": "不超过120字，回答为什么是现在；若不是当前或临近机会，也要说明现在缺少什么",
        "satisfied_conditions": ["现在已经满足的关键条件，最多4条"],
        "unmet_conditions": ["仍未满足的关键条件，最多4条"],
        "constraint_override_reason": "若判为当前机会但现价不在主报告价格规则内，必须说明为何新证据足以突破旧约束；否则留空",
        "supporting_evidence": ["直接来自输入的关键依据，最多4条"],
        "evidence_refs": [{"type": "formal_sentiment/price_rule/checklist/report/technical", "source_id": "只能从evidence_reference_catalog.source_ids逐字选择；不适用时省略", "rule_id": "只能从evidence_reference_catalog.rule_ids逐字选择；不适用时省略", "gate": "只能从evidence_reference_catalog.checklist_gates逐字选择；不适用时省略", "report_path": "只能从evidence_reference_catalog.report_paths逐字选择；不适用时省略", "date": "证据日期", "reason": "引用原因"}],
        "risks_or_counterevidence": ["直接来自输入的反面证据或不确定性，最多4条"],
        "human_questions": ["投资者最终决策前应自己核实的问题，最多4条"],
        "confidence": "仅可取：high/medium/low",
    }
    if deep:
        schema.update(
            {
                "thesis_challenge": "最多160字，专门指出最可能推翻机会判断的事实或缺口",
                "decision_boundary": "不超过100字，说明什么事实会让投资者倾向继续研究，什么事实会让其放弃；不得给出买卖/仓位指令",
            }
        )
    return schema


def review_prompts(facts: dict[str, Any], *, deep: bool, verification: bool = False) -> tuple[str, str]:
    mode = "深度复核" if deep else "全量机会扫描"
    verification_instruction = (
        "这是对Initial结果的反证复核。主动回答为什么它不是当前机会，检查Checklist hard veto、过期或冲突证据、"
        "仅C/D舆论、投资逻辑漂移，以及把执行信号误当研究机会。只能确认或降级Initial，不能升级。"
        if verification else ""
    )
    system = (
        f"你是个股研究机会识别员，正在做{mode}。你的职责是理解主报告、当前行情、技术辅助、情绪和Checklist的语义关系，"
        "判断这只股票现在是否已经出现值得投资者优先决策的正向机会。你不是投顾，不得下买入、卖出、持有、仓位或目标价指令。"
        "‘当前机会’必须能明确回答为什么是现在，并指出至少一个已经满足的关键条件；它表示当前风险收益或论文发生了正向变化。"
        "‘临近机会’表示一个具体正向触发器已经接近或部分满足，但仍有一个决定性条件未满足；它不会进入当前机会主列表。"
        "‘暂不构成当前机会’表示现在没有足够正向理由。好公司、热门叙事、估值争议、值得长期研究、未来可能跌到某价格、未来可能出现事件，"
        "以及报告需要重做，本身都不是当前或临近机会。高估值、高风险或回避案例即使很有研究价值，也不得因此判为机会。"
        "‘证据不足’只用于关键输入缺失或互相无法解释。"
        "opportunity_state是必填字段，绝不能输出空字符串、null或自造枚举；只能原样选择：当前机会、临近机会、暂不构成当前机会、证据不足。"
        "不得把本地程序的价格匹配、Checklist状态、技术状态或主报告粗标签当作自动否决器；应解释它们各自支持或反驳什么。"
        "但如果现价不在主报告任何价格规则内却仍判为当前机会，必须在constraint_override_reason中引用输入里的新事实，"
        "解释为什么该事实足以突破原约束；不能只写情绪、技术形态、好公司或值得研究。"
        "这是机会识别而非交易建议：输出中不得出现或复述买入、卖出、持有、建仓、加仓、减仓、仓位、止损、目标价、等待某价再买等动作语言，"
        "即使主报告包含这些词也不要转述。只写为何值得研究、反证是什么、以及投资者应核实哪些事实。"
        "必须只依据输入事实，不得编造外部新闻、财务数据、价格或证据ID。evidence_refs必须按字段类型逐字选自evidence_reference_catalog；"
        "报告路径只能填report_path，新闻ID只能填source_id，规则只能填rule_id，Checklist关卡只能填gate。若没有适用locator，可让非候选结论的evidence_refs为空。"
        "输出严格JSON，不要Markdown。" + verification_instruction
    )
    user = (
        f"请按以下结构输出：{json.dumps(review_schema(deep), ensure_ascii=False)}\n\n"
        f"完整事实输入：{json.dumps(facts, ensure_ascii=False)}"
    )
    return system, user


def extract_openai_chat_text(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        raise OpportunityReviewError("model response has no choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    if not isinstance(message, dict):
        raise OpportunityReviewError("model response has no message")
    content = message.get("content") or message.get("reasoning_content") or ""
    if isinstance(content, list):
        content = "".join(
            str(part.get("text") or "") for part in content if isinstance(part, dict)
        )
    return str(content or "")


def extract_anthropic_text(response: dict[str, Any]) -> str:
    content = response.get("content") or []
    if not isinstance(content, list):
        raise OpportunityReviewError("Anthropic response has no content blocks")
    text = "".join(
        str(item.get("text") or "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )
    if not text:
        raise OpportunityReviewError("Anthropic response has no text block")
    return text


def extract_responses_text(response: dict[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    blocks = response.get("output") or []
    values: list[str] = []
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict):
            continue
        for part in block.get("content") or []:
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                values.append(str(part.get("text") or ""))
    text = "".join(values).strip()
    if not text:
        raise OpportunityReviewError("Responses response has no output text")
    return text


def _parse_provider_json(raw_text: str, reasoning: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = parse_json_block(raw_text)
    except (ValueError, json.JSONDecodeError) as error:
        raise OpportunityResponseParseError(
            f"provider returned malformed JSON: {error}",
            raw_text=clean_text(raw_text, 4000),
            reasoning=reasoning,
        ) from error
    if not isinstance(parsed, dict):
        raise OpportunityResponseParseError(
            "provider did not return a JSON object",
            raw_text=clean_text(raw_text, 4000),
            reasoning=reasoning,
        )
    return parsed


def _reasoning_parameter_rejected(error: Exception) -> bool:
    text = str(error).casefold()
    parameter_named = any(token in text for token in ("reasoning", "thinking", "effort"))
    explicit_alias_rejection = any(
        phrase in text
        for phrase in ("alias rejected", "max rejected", "xhigh rejected", "high rejected")
    )
    return (parameter_named or explicit_alias_rejection) and any(
        token in text for token in ("reject", "unsupported", "invalid", "not support")
    )


def request_json(
    config: ModelConfig,
    *,
    system: str,
    user: str,
    extra_headers: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call one provider with the strongest supported reasoning request.

    Chat and Responses providers have different accepted labels.  The client
    first asks for the strongest known label and only retries an equally-high
    provider fallback when the gateway rejects that label.  It never falls
    back to disabled/low reasoning invisibly.
    """
    attempts = config.max_retries + 1
    if config.transport == TRANSPORT_OPENAI_CHAT:
        requested = config.reasoning_effort or "max"
        efforts = [requested] + (["high"] if requested == "max" else [])
        last_error: Exception | None = None
        for effective in dict.fromkeys(efforts):
            payload = {
                "model": config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": config.max_tokens,
                "thinking": {"type": "enabled"},
                "reasoning_effort": effective,
                "response_format": {"type": "json_object"},
            }
            try:
                response = http_json(
                    config.endpoint,
                    headers={
                        **(extra_headers or {}),
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                    },
                    body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=config.timeout_seconds,
                    attempts=attempts,
                )
                reasoning = {
                    "requested": f"thinking=enabled; reasoning_effort={requested}",
                    "effective": f"thinking=enabled; reasoning_effort={effective}",
                    "provider_finish_reason": ((response.get("choices") or [{}])[0] or {}).get("finish_reason"),
                    "usage": usage_summary(response),
                }
                return _parse_provider_json(extract_openai_chat_text(response), reasoning), reasoning
            except Exception as error:  # noqa: BLE001 - try the documented high fallback only
                last_error = error
                if not _reasoning_parameter_rejected(error):
                    raise
        raise OpportunityReviewError(f"highest reasoning chat request failed: {last_error}")

    if config.transport == TRANSPORT_ANTHROPIC_MESSAGES:
        budget = min(config.thinking_budget_tokens, max(1024, config.max_tokens - 1024))
        payload = {
            "model": config.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": max(config.max_tokens, budget + 1024),
            "thinking": {"type": "enabled", "budget_tokens": budget},
        }
        response = http_json(
            config.endpoint,
            headers={
                "x-api-key": config.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=config.timeout_seconds,
            attempts=attempts,
        )
        reasoning = f"thinking=enabled; budget_tokens={budget}"
        metadata = {
            "requested": reasoning,
            "effective": reasoning,
            "provider_finish_reason": response.get("stop_reason"),
        }
        return _parse_provider_json(extract_anthropic_text(response), metadata), metadata

    if config.transport == TRANSPORT_OPENAI_RESPONSES:
        requested = config.reasoning_effort or "max"
        aliases = [requested]
        if requested in {"max", "xhigh"}:
            aliases.extend(["xhigh", "high"])
        last_error = None
        for effective in dict.fromkeys(aliases):
            payload = {
                "model": config.model,
                "input": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_output_tokens": config.max_tokens,
                "reasoning": {"effort": effective},
                "text": {"format": {"type": "json_object"}},
            }
            try:
                response = http_json(
                    config.endpoint,
                    headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
                    body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=config.timeout_seconds,
                    attempts=attempts,
                )
                reasoning = {
                    "requested": f"reasoning.effort={requested}",
                    "effective": f"reasoning.effort={effective}",
                    "provider_finish_reason": response.get("status"),
                }
                return _parse_provider_json(extract_responses_text(response), reasoning), reasoning
            except Exception as error:  # noqa: BLE001 - try only xhigh/high, never a low fallback
                last_error = error
                if not _reasoning_parameter_rejected(error):
                    raise
        raise OpportunityReviewError(f"highest reasoning Responses request failed: {last_error}")

    raise OpportunityReviewError(f"unsupported transport: {config.transport}")


def normalize_opportunity_state(value: Any) -> str:
    state = clean_text(value, 30)
    return LEGACY_STATE_ALIASES.get(state, state)


def _fact_contains_reference(value: Any, field: str, expected: str) -> bool:
    if isinstance(value, dict):
        if str(value.get(field) or "") == expected:
            return True
        return any(_fact_contains_reference(item, field, expected) for item in value.values())
    if isinstance(value, list):
        return any(_fact_contains_reference(item, field, expected) for item in value)
    return False


def validate_evidence_refs(value: Any, facts: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise OpportunityReviewError("evidence_refs must be an array")
    validated: list[dict[str, str]] = []
    for raw in value[:8]:
        if not isinstance(raw, dict):
            raise OpportunityReviewError("each evidence_ref must be an object")
        ref_type = clean_text(raw.get("type"), 40)
        reason = clean_text(raw.get("reason"), 220)
        if not ref_type or not reason:
            raise OpportunityReviewError("each evidence_ref must include type and reason")
        locator_found = False
        cleaned = {"type": ref_type, "reason": reason}
        for field in ("source_id", "rule_id", "gate", "report_path"):
            expected = clean_text(raw.get(field), 300)
            if not expected:
                continue
            lookup_fields = {
                "gate": ("name",),
                "report_path": ("path", "report_path", "canonical_report", "source_report"),
            }.get(field, (field,))
            if not any(_fact_contains_reference(facts, lookup_field, expected) for lookup_field in lookup_fields):
                raise OpportunityReviewError(
                    f"evidence_ref {field} does not exist in input facts: {expected}"
                )
            cleaned[field] = expected
            locator_found = True
        if not locator_found:
            raise OpportunityReviewError("each evidence_ref needs an input-backed locator")
        evidence_date = clean_text(raw.get("date"), 40)
        if evidence_date:
            cleaned["date"] = evidence_date
        validated.append(cleaned)
    return validated


def validate_assessment(
    result: dict[str, Any],
    *,
    deep: bool,
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = normalize_opportunity_state(result.get("opportunity_state"))
    if state not in OPPORTUNITY_STATES:
        raise OpportunityReviewError(f"invalid opportunity_state: {state!r}")
    confidence = clean_text(result.get("confidence"), 20).lower()
    if confidence not in CONFIDENCE:
        raise OpportunityReviewError(f"invalid confidence: {confidence!r}")
    summary = clean_text(result.get("opportunity_summary"), 240)
    if not summary:
        raise OpportunityReviewError("opportunity_summary is empty")
    list_fields = (
        "satisfied_conditions",
        "unmet_conditions",
        "supporting_evidence",
        "risks_or_counterevidence",
        "human_questions",
        "evidence_refs",
    )
    for key in list_fields:
        if not isinstance(result.get(key, []), list):
            raise OpportunityReviewError(f"{key} must be an array")
    why_now = clean_text(result.get("why_now"), 240)
    satisfied = [
        clean_text(item, 220)
        for item in (result.get("satisfied_conditions") or [])[:4]
        if clean_text(item, 220)
    ]
    unmet = [
        clean_text(item, 220)
        for item in (result.get("unmet_conditions") or [])[:4]
        if clean_text(item, 220)
    ]
    override_reason = clean_text(result.get("constraint_override_reason"), 260)
    if state in {"当前机会", "临近机会"} and not why_now:
        raise OpportunityReviewError(f"{state} must include why_now")
    if state == "当前机会" and not satisfied:
        raise OpportunityReviewError("当前机会 must include at least one satisfied condition")
    if state == "临近机会" and not unmet:
        raise OpportunityReviewError("临近机会 must include at least one unmet condition")
    evidence_refs = validate_evidence_refs(result.get("evidence_refs", []), facts or {})
    if state in {"当前机会", "临近机会"} and not evidence_refs:
        raise OpportunityReviewError(f"{state} must include input-backed evidence_refs")
    price_status = str(((facts or {}).get("local_price_context") or {}).get("status") or "")
    if state == "当前机会" and price_status and price_status != "inside_price_rule" and not override_reason:
        raise OpportunityReviewError(
            "当前机会 outside the report price rules must include constraint_override_reason"
        )
    cleaned = {
        "opportunity_state": state,
        "opportunity_summary": summary,
        "why_now": why_now,
        "satisfied_conditions": satisfied,
        "unmet_conditions": unmet,
        "constraint_override_reason": override_reason,
        "supporting_evidence": [
            clean_text(item, 220)
            for item in (result.get("supporting_evidence") or [])[:4]
            if clean_text(item, 220)
        ],
        "evidence_refs": evidence_refs,
        "risks_or_counterevidence": [
            clean_text(item, 220)
            for item in (result.get("risks_or_counterevidence") or [])[:4]
            if clean_text(item, 220)
        ],
        "human_questions": [
            clean_text(item, 220)
            for item in (result.get("human_questions") or [])[:4]
            if clean_text(item, 220)
        ],
        "confidence": confidence,
    }
    if deep:
        challenge = clean_text(result.get("thesis_challenge"), 300)
        boundary = clean_text(result.get("decision_boundary"), 220)
        if not challenge or not boundary:
            raise OpportunityReviewError("deep review must include thesis_challenge and decision_boundary")
        cleaned["thesis_challenge"] = challenge
        cleaned["decision_boundary"] = boundary
    return cleaned


def run_model(
    config: ModelConfig,
    facts: dict[str, Any],
    *,
    deep: bool,
    verification: bool = False,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    system, user = review_prompts(facts, deep=deep, verification=verification)
    repair_attempts = 0
    validation_error_text = ""
    failure_category = ""
    try:
        try:
            raw, reasoning = request_json(
                config,
                system=system,
                user=user,
                extra_headers=extra_headers,
            )
        except OpportunityResponseParseError as parse_error:
            failure_category = "json_parse_error"
            validation_error_text = str(parse_error)
            repair_attempts = 1
            repair_user = (
                "上一次返回不是有效JSON。只修复JSON语法和完整性，不得改变事实、推理强度或结论含义。"
                f"\n解析错误：{parse_error}"
                f"\n上一次原文：{parse_error.raw_text}"
                f"\n必须满足的结构：{json.dumps(review_schema(deep), ensure_ascii=False)}"
                f"\n事实输入：{json.dumps(facts, ensure_ascii=False)}"
                "\n只输出修复后的严格JSON。"
            )
            raw, repair_reasoning = request_json(
                config,
                system=system,
                user=repair_user,
                extra_headers=extra_headers,
            )
            reasoning = {
                **repair_reasoning,
                "schema_repair": True,
                "initial_effective": parse_error.reasoning.get("effective"),
                "initial_provider_finish_reason": parse_error.reasoning.get("provider_finish_reason"),
            }
        try:
            assessment = validate_assessment(raw, deep=deep, facts=facts)
        except OpportunityReviewError as validation_error:
            validation_error_text = str(validation_error)
            failure_category = "schema_validation_error"
            if repair_attempts:
                raise
            repair_attempts = 1
            repair_user = (
                "上一次返回的JSON未通过结构校验。请重新检查输入事实并只修复结构，不得降低推理强度、改变事实或增加外部信息。"
                "\n特别注意：opportunity_state是必填字段，绝不能是空字符串、null或缺失。"
                "它只能原样取以下四个值之一：当前机会、临近机会、暂不构成当前机会、证据不足。"
                "如果事实不足以支持机会判断，就选择证据不足；不要留空，也不要自行创造其他状态。"
                f"\n校验错误：{validation_error}"
                f"\n必须满足的结构：{json.dumps(review_schema(deep), ensure_ascii=False)}"
                f"\n上一次JSON：{json.dumps(raw, ensure_ascii=False)}"
                f"\n事实输入：{json.dumps(facts, ensure_ascii=False)}"
                "\n只输出修复后的严格JSON。"
            )
            raw, repair_reasoning = request_json(
                config,
                system=system,
                user=repair_user,
                extra_headers=extra_headers,
            )
            try:
                assessment = validate_assessment(raw, deep=deep, facts=facts)
            except OpportunityReviewError as repair_error:
                validation_error_text = f"初次校验：{validation_error}；结构修复后仍失败：{repair_error}"
                raise
            reasoning = {
                **repair_reasoning,
                "schema_repair": True,
                "initial_effective": reasoning.get("effective"),
            }
        return {
            "status": "ready",
            "model": config.model,
            "transport": config.transport,
            "generated_at": now_iso(),
            "reasoning": reasoning,
            "assessment": assessment,
            "schema_repair_attempts": repair_attempts,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as error:  # noqa: BLE001 - preserve a durable per-model error
        failure_category = failure_category or error_category(error)
        provider_finish_reason = None
        if "reasoning" in locals() and isinstance(reasoning, dict):
            provider_finish_reason = reasoning.get("provider_finish_reason")
        if isinstance(error, OpportunityResponseParseError):
            provider_finish_reason = error.reasoning.get("provider_finish_reason")
        return {
            "status": "error",
            "model": config.model,
            "transport": config.transport,
            "generated_at": now_iso(),
            "reasoning": {
                "requested": "highest reasoning only",
                "effective": None,
            },
            "schema_repair_attempts": repair_attempts,
            "validation_error": validation_error_text,
            "failure_category": failure_category,
            "provider_finish_reason": provider_finish_reason,
            "error": clean_text(error, 600),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }


def union_result(models: dict[str, dict[str, Any]]) -> dict[str, Any]:
    # A stale result is useful for audit and diagnosis, but it is not evidence
    # for today's opportunity decision.  Never let a failed refresh promote an
    # old "current" or "near" assessment back into the opportunity panel.
    ready = [item for item in models.values() if item.get("status") == "ready"]
    stale = [item for item in models.values() if item.get("status") == "stale"]
    opportunities = [
        item
        for item in ready
        if normalize_opportunity_state((item.get("assessment") or {}).get("opportunity_state")) == "当前机会"
    ]
    conditional = [
        item
        for item in ready
        if normalize_opportunity_state((item.get("assessment") or {}).get("opportunity_state")) == "临近机会"
    ]
    if opportunities:
        classification = "当前机会"
    elif conditional:
        classification = "临近机会"
    elif ready:
        classification = "暂不进入机会面板"
    elif stale:
        classification = "待人工复核"
    else:
        classification = "待人工复核"
    return {
        "included": bool(opportunities),
        "near_included": bool(conditional) and not opportunities,
        "classification": classification,
        "supporting_models": [item.get("model") for item in opportunities if item.get("model")],
        "near_models": [item.get("model") for item in conditional if item.get("model")],
        "model_count": len(ready),
        "stale_count": len(stale),
        "opportunity_count": len(opportunities),
        "conditional_count": len(conditional),
        "rule": "当前机会进入主面板；临近机会单独折叠展示；最终买卖由投资者决定。",
    }


def build_scan_payload(
    configs: list[ModelConfig],
    scans: list[dict[str, Any] | None],
    *,
    workers: int,
    expected_scan_count: int,
    checkpoint: bool,
    mode: str = "full",
) -> dict[str, Any]:
    """Build a durable full-scan payload for a checkpoint or final write."""
    completed_scans = [item for item in scans if isinstance(item, dict)]
    model_results = [
        result
        for item in completed_scans
        for result in (item.get("models") or {}).values()
        if isinstance(result, dict)
    ]
    ready = sum(1 for item in model_results if item.get("status") == "ready")
    stale = sum(1 for item in model_results if item.get("status") == "stale")
    errors = sum(1 for item in model_results if item.get("status") == "error")
    complete = bool(expected_scan_count) and len(completed_scans) >= expected_scan_count
    current_opportunity_count = sum(
        1
        for item in completed_scans
        if (item.get("union") or {}).get("classification") == "当前机会"
    )
    near_opportunity_count = sum(
        1
        for item in completed_scans
        if (item.get("union") or {}).get("classification") == "临近机会"
    )
    status = (
        "ok"
        if complete and not errors and not stale
        else "partial"
        if completed_scans
        else "missing"
    )
    progress_percent = (
        round(min(100.0, len(completed_scans) * 100 / expected_scan_count), 1)
        if expected_scan_count
        else 0.0
    )
    model_request_count = sum(int(item.get("model_request_count") or 0) for item in completed_scans)
    initial_request_count = sum(1 for item in completed_scans if item.get("evaluation_mode") != "reused_unchanged")
    verification_request_count = sum(
        1 for item in completed_scans
        if item.get("evaluation_mode") != "reused_unchanged" and item.get("verification_required")
    )
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for item in completed_scans:
        for stage in (item.get("initial"), item.get("verification")):
            stage_usage = ((stage or {}).get("reasoning") or {}).get("usage") if isinstance(stage, dict) else None
            if isinstance(stage_usage, dict):
                for key in usage:
                    usage[key] += int(stage_usage.get(key) or 0)
    reused_count = sum(1 for item in completed_scans if item.get("evaluation_mode") == "reused_unchanged")
    filter_counts = {
        name: sum(1 for item in completed_scans if item.get("filter_class") == name)
        for name in (
            "unchanged", "ordinary", "possibly_material", "insufficient",
            "age_expired", "legacy_refresh",
        )
    }
    return {
        "schema_version": SCAN_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "status": status,
        "mode": mode,
        "market": MARKET,
        "models": [
            {
                "role": config.role,
                "model": config.model,
                "transport": config.transport,
                "reasoning_policy": "highest supported only",
            }
            for config in configs
        ],
        "scan_count": len(completed_scans),
        "expected_scan_count": expected_scan_count,
        "progress_percent": progress_percent,
        "checkpoint": checkpoint,
        "company_concurrency": workers,
        "model_result_count": len(model_results),
        "model_request_count": model_request_count,
        "initial_request_count": initial_request_count,
        "verification_request_count": verification_request_count,
        "token_usage": usage,
        "reused_count": reused_count,
        "filter_counts": filter_counts,
        "ready_count": ready,
        "current_opportunity_count": current_opportunity_count,
        "near_opportunity_count": near_opportunity_count,
        "stale_count": stale,
        "error_count": errors,
        "inclusion_rule": "Flash 判为当前机会才进入主面板；临近机会单独折叠展示；最终买卖由投资者决定。",
        "scans": completed_scans,
    }


def previous_model(
    previous: dict[str, Any],
    ticker: str,
    model: str,
    report_hash: str,
) -> dict[str, Any] | None:
    for record in previous.get("scans", []) if isinstance(previous, dict) else []:
        if not isinstance(record, dict) or str(record.get("ticker") or "").upper() != ticker:
            continue
        if record.get("report_sha256") != report_hash:
            return None
        found = (record.get("models") or {}).get(model)
        # Do not chain stale fallbacks.  A previous stale result already means
        # the last refresh failed; carrying it forward would make its age
        # invisible and could eventually re-enter the opportunity panel.
        if isinstance(found, dict) and found.get("status") == "ready":
            return dict(found)
    return None


def previous_scan_record(previous: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    for record in previous.get("scans", []) if isinstance(previous, dict) else []:
        if isinstance(record, dict) and str(record.get("ticker") or "").upper() == ticker:
            return record
    return None


def parsed_timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone() if parsed.tzinfo else parsed.astimezone()


def prior_opportunity_state(record: dict[str, Any], model: str) -> str:
    result = (record.get("models") or {}).get(model)
    if not isinstance(result, dict) or result.get("status") != "ready":
        return ""
    return normalize_opportunity_state((result.get("assessment") or {}).get("opportunity_state"))


def trigger_change_reasons(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    labels = {
        "report_sha256": "report_sha_changed",
        "primary_judgment": "primary_judgment_changed",
        "execution_policy": "execution_policy_changed",
        "price": "price_materiality_changed",
        "checklist": "checklist_changed",
        "daily_technical": "daily_technical_changed",
        "intraday_30m": "intraday_technical_changed",
        "sentiment": "sentiment_material_evidence_changed",
    }
    return [label for key, label in labels.items() if old.get(key) != new.get(key)]


def incremental_decision(
    prior_record: dict[str, Any] | None,
    *,
    config: ModelConfig,
    fingerprint: str,
    trigger_snapshot: dict[str, Any],
    current_input_sha256: str,
    checked_at: str,
) -> tuple[bool, str, list[str]]:
    """Return whether Flash must run, the filter class, and auditable reasons."""
    if not prior_record:
        return True, "insufficient", ["no_previous_assessment"]
    old_fingerprint = prior_record.get("material_trigger_fingerprint")
    old_snapshot = prior_record.get("material_trigger_snapshot")
    old_contract = prior_record.get("assessment_contract")
    if not old_fingerprint or not isinstance(old_snapshot, dict) or not isinstance(old_contract, dict):
        return True, "legacy_refresh", ["legacy_missing_incremental_contract"]
    if old_contract != assessment_contract(config):
        return True, "possibly_material", ["assessment_contract_changed"]
    if old_fingerprint != fingerprint:
        reasons = trigger_change_reasons(old_snapshot, trigger_snapshot)
        return True, "possibly_material", reasons or ["material_trigger_changed"]

    model_result = (prior_record.get("models") or {}).get(config.model)
    if not isinstance(model_result, dict) or model_result.get("status") != "ready":
        return True, "insufficient", ["previous_model_result_not_ready"]
    prior_generated = parsed_timestamp(model_result.get("generated_at") or prior_record.get("generated_at"))
    current_time = parsed_timestamp(checked_at)
    if not prior_generated or not current_time:
        return True, "age_expired", ["model_evaluation_age_unknown"]
    state = prior_opportunity_state(prior_record, config.model)
    if state in {"当前机会", "临近机会"} and prior_generated.date() < current_time.date():
        return True, "age_expired", ["current_or_near_requires_daily_refresh"]
    if current_time - prior_generated > timedelta(days=MAX_REUSE_AGE_DAYS):
        return True, "age_expired", ["maximum_reuse_age_exceeded"]
    exact_unchanged = prior_record.get("input_sha256") == current_input_sha256
    return False, "unchanged" if exact_unchanged else "ordinary", [
        "material_trigger_unchanged"
    ]


def scan_one(
    decision: dict[str, Any],
    *,
    repo_root: Path,
    configs: list[ModelConfig],
    sentiment_by_ticker: dict[str, Any],
    intraday_by_ticker: dict[str, Any],
    quote_by_ticker: dict[str, Any],
    previous: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
    mode: str = "full",
) -> dict[str, Any]:
    ticker = str(decision.get("ticker") or "").upper()
    current_hash = report_sha256(repo_root, decision)
    facts = build_opportunity_input(
        decision,
        repo_root=repo_root,
        sentiment=sentiment_by_ticker.get(ticker),
        intraday=intraday_by_ticker.get(ticker),
        quote=quote_by_ticker.get(ticker),
    )
    checked_at = now_iso()
    trigger_snapshot = material_trigger_snapshot(facts, current_hash)
    trigger_fingerprint = stable_sha256(trigger_snapshot)
    prior_record = previous_scan_record(previous, ticker)
    contract = assessment_contract(configs[0])
    if mode == "incremental":
        should_evaluate, filter_class, trigger_reasons = incremental_decision(
            prior_record,
            config=configs[0],
            fingerprint=trigger_fingerprint,
            trigger_snapshot=trigger_snapshot,
            current_input_sha256=str(facts.get("input_sha256") or ""),
            checked_at=checked_at,
        )
    else:
        should_evaluate, filter_class, trigger_reasons = True, "possibly_material", ["full_reconciliation"]

    if not should_evaluate and prior_record:
        preserved_models = {
            key: dict(value)
            for key, value in (prior_record.get("models") or {}).items()
            if isinstance(value, dict)
        }
        model_generated = [
            str(value.get("generated_at"))
            for value in preserved_models.values()
            if value.get("generated_at")
        ]
        return {
            "schema_version": SCAN_SCHEMA_VERSION,
            "status": "ready",
            "company": decision.get("company"),
            "ticker": ticker,
            "market": decision.get("market"),
            "report_path": decision.get("report_path"),
            "report_sha256": current_hash,
            # These remain the exact model input and provenance from the
            # original evaluation. Current facts are stored separately below.
            "input_sha256": prior_record.get("input_sha256"),
            "generated_at": prior_record.get("generated_at"),
            "models": preserved_models,
            "union": union_result(preserved_models),
            "initial": prior_record.get("initial"),
            "verification": prior_record.get("verification"),
            "final": prior_record.get("final") or next(iter(preserved_models.values()), None),
            "verification_required": bool(prior_record.get("verification_required")),
            "input_snapshot": prior_record.get("input_snapshot"),
            "evaluation_mode": "reused_unchanged",
            "model_request_count": 0,
            "filter_class": filter_class,
            "trigger_reasons": trigger_reasons,
            "assessment_contract": contract,
            "material_trigger_fingerprint": trigger_fingerprint,
            "material_trigger_snapshot": trigger_snapshot,
            "material_trigger_checked_at": checked_at,
            "last_model_evaluated_at": min(model_generated) if model_generated else None,
            "reused_from_generated_at": prior_record.get("generated_at"),
            "current_projection_context": {
                "current_input_sha256": facts.get("input_sha256"),
                "material_trigger_snapshot": trigger_snapshot,
            },
        }
    initial_config = configs[0]
    verifier_config = configs[1] if len(configs) > 1 else ModelConfig(
        role="opportunity_verify",
        model=initial_config.model,
        transport=initial_config.transport,
        endpoint=initial_config.endpoint,
        api_key=initial_config.api_key,
        max_tokens=initial_config.max_tokens,
        timeout_seconds=initial_config.timeout_seconds,
        max_retries=initial_config.max_retries,
        reasoning_effort="max",
        thinking_budget_tokens=initial_config.thinking_budget_tokens,
    )
    initial = run_model(
        initial_config, facts, deep=False, extra_headers=extra_headers
    )
    request_count = 1
    initial_state = normalize_opportunity_state(
        ((initial.get("assessment") or {}).get("opportunity_state"))
    ) if initial.get("status") == "ready" else ""
    verification_required = initial_state in {"当前机会", "临近机会"}
    verification: dict[str, Any] | None = None
    if verification_required:
        verification_facts = {
            **facts,
            "initial_opportunity_assessment": initial.get("assessment"),
            "verification_contract": {
                "cannot_promote": True,
                "purpose": "challenge the initial candidate and confirm or downgrade it",
            },
        }
        verification = run_model(
            verifier_config,
            verification_facts,
            deep=False,
            verification=True,
            extra_headers=extra_headers,
        )
        request_count += 1

    final_result = dict(initial)
    if verification_required:
        if not verification or verification.get("status") != "ready":
            final_result = {
                "status": "error",
                "model": initial_config.model,
                "transport": initial_config.transport,
                "generated_at": now_iso(),
                "failure_category": "verification_failed",
                "error": "candidate verification did not produce a valid result",
            }
        else:
            verified_assessment = dict(verification.get("assessment") or {})
            verified_state = normalize_opportunity_state(verified_assessment.get("opportunity_state"))
            rank = {"证据不足": 0, "暂不构成当前机会": 0, "临近机会": 1, "当前机会": 2}
            if rank.get(verified_state, 0) > rank.get(initial_state, 0):
                verified_assessment["opportunity_state"] = initial_state
                verified_assessment["verification_policy_note"] = "promotion rejected by policy"
            final_result = {**verification, "assessment": verified_assessment, "model": initial_config.model}

    if final_result.get("status") == "error":
        fallback = previous_model(previous, ticker, initial_config.model, current_hash)
        if fallback:
            fallback["status"] = "stale"
            fallback["stale_reason"] = final_result.get("error")
            fallback["last_attempt_at"] = final_result.get("generated_at")
            final_result = fallback
    models: dict[str, dict[str, Any]] = {initial_config.model: final_result}
    refresh_failed = any(item.get("status") != "ready" for item in models.values())
    preserved_input = (
        prior_record.get("input_snapshot")
        if refresh_failed and prior_record and any(item.get("status") == "stale" for item in models.values())
        else facts
    )
    preserved_input_sha = (
        prior_record.get("input_sha256")
        if preserved_input is not facts and prior_record
        else facts.get("input_sha256")
    )
    model_generated = [str(item.get("generated_at")) for item in models.values() if item.get("generated_at")]
    return {
        "schema_version": SCAN_SCHEMA_VERSION,
        "status": "ready" if all(item.get("status") == "ready" for item in models.values()) else "partial",
        "company": decision.get("company"),
        "ticker": ticker,
        "market": decision.get("market"),
        "report_path": decision.get("report_path"),
        "report_sha256": current_hash,
        "input_sha256": preserved_input_sha,
        "generated_at": checked_at,
        "models": models,
        "union": union_result(models),
        "initial": initial,
        "verification": verification,
        "final": final_result,
        "verification_required": verification_required,
        "input_snapshot": preserved_input,
        "evaluation_mode": "refresh_failed" if refresh_failed else "model_evaluated",
        "model_request_count": request_count,
        "filter_class": filter_class,
        "trigger_reasons": trigger_reasons,
        "assessment_contract": contract,
        "material_trigger_fingerprint": trigger_fingerprint,
        "material_trigger_snapshot": trigger_snapshot,
        "material_trigger_checked_at": checked_at,
        "last_model_evaluated_at": min(model_generated) if model_generated and not refresh_failed else (
            prior_record.get("last_model_evaluated_at") if prior_record else None
        ),
        "current_projection_context": {
            "current_input_sha256": facts.get("input_sha256"),
            "material_trigger_snapshot": trigger_snapshot,
        } if refresh_failed else None,
    }


def scan_all(
    repo_root: Path,
    *,
    ticker: str | None = None,
    limit: int | None = None,
    previous: dict[str, Any] | None = None,
    checkpoint_path: Path | None = None,
    mode: str = "full",
) -> dict[str, Any]:
    if mode not in {"full", "incremental"}:
        raise OpportunityReviewError(f"unsupported scan mode: {mode}")
    configs = [model_config("opportunity_initial"), model_config("opportunity_verify")]
    scan_headers = opportunity_scan_headers()
    decisions = find_decisions(repo_root, ticker)
    if limit is not None:
        decisions = decisions[: max(0, limit)]
    sentiment, intraday, quotes = snapshot_maps(repo_root)
    prior = previous if isinstance(previous, dict) else {}
    # A small bounded company-level pool keeps a full after-close scan practical.
    # The default means at most three model requests are in flight, avoiding a burst that
    # could exhaust provider concurrency or rate limits.
    workers = parse_integer(os.environ.get("OPPORTUNITY_SCAN_CONCURRENCY"), 3, 1, 6)
    scans: list[dict[str, Any] | None] = [None] * len(decisions)
    checkpoint_targets = {
        math.ceil(len(decisions) * step / 10)
        for step in range(1, 11)
        if decisions
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(decisions) or 1)) as executor:
        futures = {
            executor.submit(
                scan_one,
                decision,
                repo_root=repo_root,
                configs=configs,
                sentiment_by_ticker=sentiment,
                intraday_by_ticker=intraday,
                quote_by_ticker=quotes,
                previous=prior,
                extra_headers=scan_headers,
                mode=mode,
            ): index
            for index, decision in enumerate(decisions)
        }
        for completed, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            index = futures[future]
            scans[index] = future.result()
            scanned = scans[index] or {}
            print(
                f"AI opportunity scan progress {completed}/{len(decisions)} · "
                f"{scanned.get('ticker') or 'unknown'} · {scanned.get('status') or 'unknown'}",
                flush=True,
            )
            if (
                checkpoint_path
                and completed in checkpoint_targets
                and completed < len(decisions)
            ):
                write_json(
                    checkpoint_path,
                    build_scan_payload(
                        configs,
                        scans,
                        workers=min(workers, len(decisions) or 1),
                        expected_scan_count=len(decisions),
                        checkpoint=True,
                        mode=mode,
                    ),
                )
    payload = build_scan_payload(
        configs,
        scans,
        workers=min(workers, len(decisions) or 1),
        expected_scan_count=len(decisions),
        checkpoint=False,
        mode=mode,
    )
    if checkpoint_path:
        write_json(checkpoint_path, payload)
    return payload


def deep_review_one(repo_root: Path, ticker: str) -> dict[str, Any]:
    config = model_config("opportunity_deep")
    decision = find_decisions(repo_root, ticker)[0]
    ticker_upper = str(decision.get("ticker") or "").upper()
    sentiment, intraday, quotes = snapshot_maps(repo_root)
    facts = build_opportunity_input(
        decision,
        repo_root=repo_root,
        sentiment=sentiment.get(ticker_upper),
        intraday=intraday.get(ticker_upper),
        quote=quotes.get(ticker_upper),
    )
    models = {config.model: run_model(config, facts, deep=True)}
    ready = [item for item in models.values() if item.get("status") == "ready"]
    states = [str((item.get("assessment") or {}).get("opportunity_state") or "") for item in ready]
    return {
        "schema_version": DEEP_SCHEMA_VERSION,
        "status": "ready" if ready else "error",
        "company": decision.get("company"),
        "ticker": ticker_upper,
        "market": decision.get("market"),
        "report_path": decision.get("report_path"),
        "report_sha256": report_sha256(repo_root, decision),
        "input_sha256": facts.get("input_sha256"),
        "generated_at": now_iso(),
        "models": models,
        "synthesis": {
            "state_agreement": "单模型MAX反证复核" if ready else "结果不完整",
            "rule": "DeepSeek Flash MAX 仅提供反证复核；最终决定属于投资者。",
        },
        "input_snapshot": facts,
    }


def update_deep_payload(existing: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    reviews = [
        item
        for item in existing.get("reviews", []) if isinstance(item, dict) and item.get("ticker") != review.get("ticker")
    ]
    reviews.append(review)
    reviews.sort(key=lambda item: str(item.get("ticker") or ""))
    return {
        "schema_version": DEEP_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "status": "ok" if reviews else "missing",
        "review_count": len(reviews),
        "reviews": reviews,
        "access": "仅经受保护的深度复核接口读取；不写入公开静态站。",
    }


def command_scan(arguments: argparse.Namespace) -> int:
    repo_root = arguments.repo_root.resolve()
    output = arguments.output if arguments.output.is_absolute() else repo_root / arguments.output
    prior = load_json(output, {})
    payload = scan_all(
        repo_root,
        ticker=arguments.ticker,
        limit=arguments.limit,
        previous=prior,
        checkpoint_path=output,
        mode=arguments.mode,
    )
    print(
        f"Wrote {output} · {payload['mode']} · {payload['ready_count']} ready · "
        f"{payload['model_request_count']} model requests · {payload['reused_count']} reused · "
        f"{payload['current_opportunity_count']} current · "
        f"{payload['near_opportunity_count']} near · "
        f"{payload['stale_count']} stale · {payload['error_count']} error",
        flush=True,
    )
    # ``ready_count`` counts valid model responses, not opportunities. A
    # complete scan with zero current/near opportunities is a successful and
    # important result, so it must not be reported as a failed job.
    return 0 if payload["status"] == "ok" else 2


def command_retry_failed(arguments: argparse.Namespace) -> int:
    repo_root = arguments.repo_root.resolve()
    output = arguments.output if arguments.output.is_absolute() else repo_root / arguments.output
    previous = load_json(output, {})
    previous_scans = [item for item in previous.get("scans", []) if isinstance(item, dict)]
    if not previous_scans:
        raise OpportunityReviewError("retry-failed requires an existing full scan payload")
    requested = str(arguments.ticker or "").upper()
    failed_tickers = [
        str(item.get("ticker") or "").upper()
        for item in previous_scans
        if any(
            result.get("status") != "ready"
            for result in (item.get("models") or {}).values()
            if isinstance(result, dict)
        )
    ]
    targets = [requested] if requested else failed_tickers
    if requested and requested not in {str(item.get("ticker") or "").upper() for item in previous_scans}:
        raise OpportunityReviewError(f"ticker is not in existing scan: {requested}")
    replacements: dict[str, dict[str, Any]] = {}
    for ticker in targets:
        retry = scan_all(repo_root, ticker=ticker, previous=previous, mode="full")
        if len(retry.get("scans") or []) != 1:
            raise OpportunityReviewError(f"retry did not return exactly one scan: {ticker}")
        replacements[ticker] = retry["scans"][0]
    merged = [replacements.get(str(item.get("ticker") or "").upper(), item) for item in previous_scans]
    configs = [model_config("opportunity_initial"), model_config("opportunity_verify")]
    payload = build_scan_payload(
        configs,
        merged,
        workers=1,
        expected_scan_count=int(previous.get("expected_scan_count") or len(previous_scans)),
        checkpoint=False,
        mode="retry_failed",
    )
    payload["retry"] = {"requested": targets, "replaced_count": len(replacements)}
    write_json(output, payload)
    print(
        f"Wrote {output} · retried {len(replacements)} · {payload['ready_count']} ready · "
        f"{payload['stale_count']} stale · {payload['error_count']} error",
        flush=True,
    )
    return 0 if payload["status"] == "ok" else 2


def command_deep(arguments: argparse.Namespace) -> int:
    repo_root = arguments.repo_root.resolve()
    output = arguments.output if arguments.output.is_absolute() else repo_root / arguments.output
    review = deep_review_one(repo_root, arguments.ticker)
    payload = update_deep_payload(load_json(output, {}), review)
    write_json(output, payload)
    print(f"Wrote {output} · {review['ticker']} · {review['status']}", flush=True)
    return 0 if review["status"] == "ready" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="scan all A shares with Flash")
    scan.add_argument("--repo-root", type=Path, default=ROOT)
    scan.add_argument("--ticker")
    scan.add_argument("--limit", type=int)
    scan.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default="full",
        help="full always evaluates every ticker; incremental reuses only contract-safe assessments",
    )
    scan.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "opportunity_scans.json",
    )
    scan.set_defaults(handler=command_scan)
    retry = subparsers.add_parser("retry-failed", help="retry only failed/stale tickers and merge into the existing full set")
    retry.add_argument("--repo-root", type=Path, default=ROOT)
    retry.add_argument("--ticker")
    retry.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "opportunity_scans.json",
    )
    retry.set_defaults(handler=command_retry_failed)
    deep = subparsers.add_parser("deep", help="run DeepSeek Flash MAX for one ticker")
    deep.add_argument("--repo-root", type=Path, default=ROOT)
    deep.add_argument("--ticker", required=True)
    deep.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "deep_opportunity_reviews.json",
    )
    deep.set_defaults(handler=command_deep)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        return arguments.handler(arguments)
    except (OSError, OpportunityReviewError, SentimentError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
