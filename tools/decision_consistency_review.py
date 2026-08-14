#!/usr/bin/env python3
"""Use one DeepSeek model to explain consistency across dashboard layers.

The model is an auxiliary reviewer. It never writes the primary judgment,
execution policy, price rules, technical state, sentiment score, or Checklist
status. A failed call produces an explicit error artifact instead of a fallback
recommendation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEW_MARKET = "A股"
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402
import report_judgment  # noqa: E402
from sentiment_snapshot import LLMConfig, http_json, parse_json_block  # noqa: E402


REVIEW_ALIGNMENTS = {"一致", "条件一致", "存在冲突", "数据不足"}
REVIEW_ATTENTION = {"常规", "注意", "待复核"}
REVIEW_FOCUS = {
    "主报告条件",
    "当前价格",
    "日线技术面",
    "30分钟技术面",
    "情绪",
    "Checklist",
    "数据不足",
}
REVIEW_CONFIDENCE = {"high", "medium", "low"}


class ConsistencyReviewError(RuntimeError):
    """Raised when the consistency review cannot be trusted."""


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def clean_text(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def load_model_config(model_override: str | None) -> LLMConfig:
    """Reuse the configured OpenCode Go key/endpoint without exposing secrets."""
    report_judgment.load_model_environment()
    dedicated = LLMConfig.from_environment("DECISION_REVIEW_")
    if dedicated:
        return replace(dedicated, model=model_override or dedicated.model)
    base = LLMConfig.from_environment("SENTIMENT_LLM_")
    if base is None:
        raise ConsistencyReviewError(
            "missing model configuration; configure the shared OpenCode Go key and SENTIMENT_LLM_* settings"
        )
    return replace(base, model=model_override or os.environ.get("DECISION_REVIEW_MODEL") or base.model or "deepseek-v4-flash")


def find_decisions(board_path: Path, ticker: str | None, company: str | None) -> list[dict[str, Any]]:
    payload = load_json(board_path, {})
    decisions = payload.get("decisions") if isinstance(payload, dict) else None
    if not isinstance(decisions, list):
        raise ConsistencyReviewError(f"invalid decision board: {board_path}")
    ticker_upper = ticker.upper() if ticker else None
    selected = [
        item
        for item in decisions
        if isinstance(item, dict)
        and str(item.get("market") or "") == REVIEW_MARKET
        and (not ticker_upper or str(item.get("ticker") or "").upper() == ticker_upper)
        and (not company or str(item.get("company") or "") == company)
        and item.get("report_path")
    ]
    if ticker_upper and not selected:
        raise ConsistencyReviewError(f"ticker not found in decision board: {ticker_upper}")
    if company and not selected:
        raise ConsistencyReviewError(f"company not found in decision board: {company}")
    return sorted(selected, key=lambda item: (str(item.get("company") or ""), str(item.get("ticker") or "")))


def price_context(policy: dict[str, Any], quote: dict[str, Any] | None) -> dict[str, Any]:
    """Evaluate simple price-rule membership locally before asking the model."""
    price = finite_number((quote or {}).get("price"))
    rules = policy.get("price_rules") if isinstance(policy, dict) else []
    if price is None:
        return {"status": "no_current_quote", "price": None, "matched_rules": []}
    matched: list[dict[str, Any]] = []
    ceilings: list[float] = []
    for rule in rules if isinstance(rules, list) else []:
        if not isinstance(rule, dict):
            continue
        ceiling = finite_number(rule.get("ceiling"))
        minimum = finite_number(rule.get("min"))
        if ceiling is not None:
            ceilings.append(ceiling)
        in_rule = ceiling is not None and price <= ceiling and (minimum is None or price >= minimum)
        if in_rule:
            matched.append(
                {
                    "action_kind": rule.get("action_kind"),
                    "action": clean_text(rule.get("action"), 80),
                    "price_range": clean_text(rule.get("price_range"), 80),
                    "requires_validation": rule.get("requires_validation") is True,
                    "validation_condition": clean_text(rule.get("validation_condition"), 140),
                }
            )
    if matched:
        status = "inside_price_rule"
    elif ceilings and price > max(ceilings):
        status = "above_all_entry_rules"
    else:
        status = "below_or_outside_price_rules"
    return {
        "status": status,
        "price": price,
        "currency": (quote or {}).get("currency"),
        "matched_rules": matched,
        "rule_ceiling_max": max(ceilings) if ceilings else None,
        "calculation": "本地程序按 execution_policy.price_rules 确定性匹配；模型不得重算价格",
    }


def compact_technical(technical: dict[str, Any] | None) -> dict[str, Any]:
    technical = technical if isinstance(technical, dict) else {}
    return {
        "status": technical.get("status", "missing"),
        "state": technical.get("state", "待复核"),
        "data_cutoff": technical.get("data_cutoff"),
        "latest_price": technical.get("latest_price"),
        "observation_zone": technical.get("observation_zone"),
        "combined_candidate_zone": technical.get("combined_candidate_zone"),
        "valid_buy_candidate": technical.get("valid_buy_candidate"),
        "lights": [
            {
                "dimension": item.get("dimension"),
                "light": item.get("light"),
                "meaning": clean_text(item.get("meaning"), 120),
            }
            for item in technical.get("lights", [])
            if isinstance(item, dict)
        ],
    }


def compact_intraday(technical: dict[str, Any] | None) -> dict[str, Any]:
    technical = technical if isinstance(technical, dict) else {}
    return {
        "status": technical.get("status", "missing"),
        "state": technical.get("technical_state", "待复核"),
        "reason": clean_text(technical.get("technical_reason"), 180),
        "data_cutoff": technical.get("data_cutoff"),
        "bar_timestamp": technical.get("bar_timestamp"),
        "latest": technical.get("latest") if isinstance(technical.get("latest"), dict) else {},
        "trend": technical.get("trend") if isinstance(technical.get("trend"), dict) else {},
        "momentum": technical.get("momentum") if isinstance(technical.get("momentum"), dict) else {},
        "volatility": technical.get("volatility") if isinstance(technical.get("volatility"), dict) else {},
        "session": technical.get("intraday") if isinstance(technical.get("intraday"), dict) else {},
    }


def compact_sentiment(record: dict[str, Any] | None) -> dict[str, Any]:
    record = record if isinstance(record, dict) else {}
    news = record.get("news_sentiment") if isinstance(record.get("news_sentiment"), dict) else {}
    combined = record.get("combined_sentiment") if isinstance(record.get("combined_sentiment"), dict) else {}
    items = news.get("items") if isinstance(news.get("items"), list) else []
    scored = [
        {
            "title": clean_text(item.get("title"), 100),
            "published_at": item.get("published_at"),
            "event_type": item.get("event_type"),
            "direction": item.get("direction"),
            "impact": item.get("impact"),
            "source_tier": item.get("source_tier"),
        }
        for item in items[:5]
        if isinstance(item, dict)
    ]
    return {
        "status": record.get("status", "missing"),
        "data_cutoff": record.get("data_cutoff"),
        "combined": {
            "score_0_100": combined.get("score_0_100"),
            "state": combined.get("state"),
        },
        "news": {
            "score_0_100": news.get("score_0_100"),
            "state": news.get("state"),
            "confidence": news.get("confidence"),
            "score_article_count": news.get("score_article_count"),
            "auxiliary_article_count": news.get("auxiliary_article_count"),
        },
        "scored_news_examples": scored,
    }


def compact_checklist(checklist: dict[str, Any] | None) -> dict[str, Any]:
    checklist = checklist if isinstance(checklist, dict) else {}
    gates = checklist.get("gates") if isinstance(checklist.get("gates"), list) else []
    return {
        "status": checklist.get("status", "missing"),
        "hard_veto": checklist.get("hard_veto"),
        "hard_veto_label": checklist.get("hard_veto_label"),
        "mirror_test": checklist.get("mirror_test"),
        "confidence": checklist.get("confidence"),
        "summary": clean_text(checklist.get("summary"), 180),
        "data_cutoff": checklist.get("data_cutoff"),
        "gates": [
            {
                "name": gate.get("name"),
                "result": gate.get("result"),
                "reason": clean_text(gate.get("reason"), 120),
            }
            for gate in gates
            if isinstance(gate, dict)
        ],
    }


def build_review_input(
    decision: dict[str, Any],
    *,
    repo_root: Path,
    sentiment: dict[str, Any] | None,
    intraday: dict[str, Any] | None,
    quote: dict[str, Any] | None,
) -> dict[str, Any]:
    report_path = repo_root / str(decision["report_path"])
    if not report_path.is_file():
        raise ConsistencyReviewError(f"main report does not exist: {decision['report_path']}")
    lines = report_path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        excerpt, _allowed_lines = report_judgment.decision_excerpt(lines)
    except report_judgment.JudgmentError:
        excerpt = "\n".join(f"L{index + 1}: {line}" for index, line in enumerate(lines[:120]))
    judgment = decision.get("primary_judgment") if isinstance(decision.get("primary_judgment"), dict) else {}
    policy = decision.get("execution_policy") if isinstance(decision.get("execution_policy"), dict) else {}
    facts = {
        "company": decision.get("company"),
        "ticker": decision.get("ticker"),
        "market": decision.get("market"),
        "report": {
            "path": decision.get("report_path"),
            "data_cutoff": decision.get("data_cutoff"),
            "excerpt": excerpt,
        },
        "primary_judgment": {
            key: judgment.get(key)
            for key in (
                "label",
                "action_kind",
                "empty_position_action",
                "holder_action",
                "trigger_condition",
                "summary",
                "confidence",
                "report_field_conflict",
                "conflict_note",
                "artifact_status",
                "source_matches",
                "model_consensus",
            )
        },
        "execution_policy": {
            "main_label": policy.get("main_label"),
            "condition_mode": policy.get("condition_mode"),
            "event_condition": policy.get("event_condition"),
            "guard_condition": policy.get("guard_condition"),
            "price_rules": [
                {
                    key: rule.get(key)
                    for key in (
                        "action_kind",
                        "action",
                        "price_range",
                        "min",
                        "ceiling",
                        "requires_validation",
                        "validation_condition",
                    )
                }
                for rule in policy.get("price_rules", [])
                if isinstance(rule, dict)
            ],
            "reliability": policy.get("reliability"),
        },
        "current_quote": {
            key: (quote or {}).get(key)
            for key in (
                "price",
                "previous_close",
                "change_pct",
                "currency",
                "generated_at",
                "provider_timestamp",
                "source",
            )
        },
        "local_price_context": price_context(policy, quote),
        "daily_technical": compact_technical(decision.get("technical_analysis")),
        "intraday_30m": compact_intraday(intraday),
        "sentiment": compact_sentiment(sentiment),
        "checklist": compact_checklist(decision.get("checklist")),
    }
    encoded = json.dumps(facts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    facts["input_sha256"] = hashlib.sha256(encoded).hexdigest()
    return facts


def call_review_model(config: LLMConfig, facts: dict[str, Any]) -> dict[str, Any]:
    system_prompt = (
        "你是投资决策看板的跨模块一致性审阅员。你只能解释输入事实之间是否一致，不能提出新的投资观点，"
        "不能修改主报告判断、粗颗粒度筛选、价格规则、技术指标、情绪分数或Checklist结论。"
        "主报告判断始终优先；当前价格匹配由本地程序完成；技术面和情绪只能作为辅助。"
        "如果数据缺失，必须标记数据不足，不得自行补全。只返回严格JSON，不要Markdown。"
    )
    schema = {
        "alignment": "仅可取：一致/条件一致/存在冲突/数据不足",
        "attention": "仅可取：常规/注意/待复核",
        "focus": "仅可取：主报告条件/当前价格/日线技术面/30分钟技术面/情绪/Checklist/数据不足",
        "satisfied_conditions": ["已经满足的输入条件，最多4条"],
        "missing_conditions": ["尚未满足或无法确认的输入条件，最多4条"],
        "conflicts": ["不同模块之间的具体冲突，最多3条；没有则为空数组"],
        "explanation": "不超过120字，只解释输入事实",
        "confidence": "仅可取：high/medium/low",
    }
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"请审阅以下结构化事实。不要输出买入、卖出或新的价格建议。\n"
                    f"输出结构：{json.dumps(schema, ensure_ascii=False)}\n\n"
                    f"输入事实：{json.dumps(facts, ensure_ascii=False)}"
                ),
            },
        ],
        "max_tokens": max(900, config.max_tokens or 0),
    }
    if config.thinking_mode:
        payload["thinking"] = {"type": config.thinking_mode}
    if config.json_mode:
        payload["response_format"] = {"type": "json_object"}
    response = http_json(
        config.endpoint,
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=config.timeout_seconds,
        attempts=config.max_retries + 1,
        retry_backoff_seconds=config.retry_backoff_seconds,
    )
    choices = response.get("choices") or []
    if not choices:
        raise ConsistencyReviewError("model response has no choices")
    message = choices[0].get("message") or {}
    content = message.get("content") or message.get("reasoning_content") or ""
    parsed = parse_json_block(content)
    if not isinstance(parsed, dict):
        raise ConsistencyReviewError("model response is not a JSON object")
    return parsed


def validate_review(result: dict[str, Any]) -> dict[str, Any]:
    alignment = str(result.get("alignment") or "").strip()
    attention = str(result.get("attention") or "").strip()
    focus = str(result.get("focus") or "").strip()
    confidence = str(result.get("confidence") or "").strip().lower()
    if alignment not in REVIEW_ALIGNMENTS:
        raise ConsistencyReviewError(f"invalid alignment: {alignment!r}")
    if attention not in REVIEW_ATTENTION:
        raise ConsistencyReviewError(f"invalid attention: {attention!r}")
    if focus not in REVIEW_FOCUS:
        raise ConsistencyReviewError(f"invalid focus: {focus!r}")
    if confidence not in REVIEW_CONFIDENCE:
        raise ConsistencyReviewError(f"invalid confidence: {confidence!r}")
    arrays: dict[str, list[str]] = {}
    for key, maximum in (("satisfied_conditions", 4), ("missing_conditions", 4), ("conflicts", 3)):
        value = result.get(key, [])
        if not isinstance(value, list):
            raise ConsistencyReviewError(f"{key} must be an array")
        arrays[key] = [clean_text(item, 160) for item in value[:maximum] if clean_text(item, 160)]
    explanation = clean_text(result.get("explanation"), 240)
    if not explanation:
        raise ConsistencyReviewError("model explanation is empty")
    return {
        "alignment": alignment,
        "attention": attention,
        "focus": focus,
        **arrays,
        "explanation": explanation,
        "confidence": confidence,
    }


def failed_review(
    decision: dict[str, Any],
    facts: dict[str, Any],
    error: Exception,
    model: str,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "error",
        "company": decision.get("company"),
        "ticker": decision.get("ticker"),
        "market": decision.get("market"),
        "report_path": decision.get("report_path"),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "report_sha256": hashlib.sha256(
            (repo_root / str(decision["report_path"])).read_bytes()
        ).hexdigest(),
        "model": model,
        "input_sha256": facts.get("input_sha256"),
        "screening_effect": "不改变主报告和粗颗粒度筛选",
        "error": clean_text(error, 500),
        "review": None,
    }


def review_one(decision: dict[str, Any], repo_root: Path, config: LLMConfig) -> dict[str, Any]:
    sentiment_snapshot = load_json(repo_root / "site" / "data" / "sentiment.json", {})
    sentiment_by_ticker = {
        str(item.get("ticker") or "").upper(): item
        for item in sentiment_snapshot.get("companies", [])
        if isinstance(item, dict) and item.get("ticker")
    }
    intraday_snapshot = load_json(
        repo_root / "data" / "investment-dashboard" / "intraday_technical.json",
        {"companies": []},
    )
    intraday_by_ticker = {
        str(item.get("ticker") or "").upper(): item
        for item in intraday_snapshot.get("companies", [])
        if isinstance(item, dict) and item.get("ticker")
    }
    quotes_snapshot = load_json(
        repo_root / "data" / "investment-dashboard" / "quotes" / "latest.json",
        {"quotes": []},
    )
    quote_by_ticker = {
        str(item.get("ticker") or "").upper(): item
        for item in quotes_snapshot.get("quotes", [])
        if isinstance(item, dict) and item.get("ticker")
    }
    ticker = str(decision.get("ticker") or "").upper()
    try:
        facts = build_review_input(
            decision,
            repo_root=repo_root,
            sentiment=sentiment_by_ticker.get(ticker),
            intraday=intraday_by_ticker.get(ticker),
            quote=quote_by_ticker.get(ticker),
        )
    except Exception as error:  # noqa: BLE001 - data failures also fail closed
        return failed_review(decision, {}, error, config.model, repo_root)
    started = time.perf_counter()
    try:
        review = validate_review(call_review_model(config, facts))
    except Exception as error:  # noqa: BLE001 - fail closed into a durable artifact
        result = failed_review(decision, facts, error, config.model, repo_root)
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        return result
    return {
        "schema_version": 1,
        "status": "ready",
        "company": decision.get("company"),
        "ticker": ticker,
        "market": decision.get("market"),
        "report_path": decision.get("report_path"),
        "report_sha256": hashlib.sha256(
            (repo_root / str(decision["report_path"])).read_bytes()
        ).hexdigest(),
        "model": config.model,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_sha256": facts.get("input_sha256"),
        "screening_effect": "不改变主报告和粗颗粒度筛选",
        "review": review,
        "input_snapshot": facts,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--ticker")
    parser.add_argument("--company")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", help="model id; defaults to DECISION_REVIEW_MODEL or the configured SENTIMENT_LLM_MODEL")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "decision_reviews.json",
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    board_path = repo_root / "data" / "investment-dashboard" / "decision_board.json"
    config = load_model_config(arguments.model)
    decisions = find_decisions(board_path, arguments.ticker, arguments.company)
    if arguments.limit is not None:
        decisions = decisions[: max(arguments.limit, 0)]
    reviews: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions, start=1):
        result = review_one(decision, repo_root, config)
        reviews.append(result)
        marker = "完成" if result["status"] == "ready" else "失败"
        print(f"[{index}/{len(decisions)}] {decision.get('company')} {decision.get('ticker')}: {marker}")
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "ok" if reviews and all(item["status"] == "ready" for item in reviews) else "partial" if reviews else "missing",
        "model": config.model,
        "review_count": len(reviews),
        "ready_count": sum(item["status"] == "ready" for item in reviews),
        "error_count": sum(item["status"] == "error" for item in reviews),
        "reviews": reviews,
    }
    output = arguments.output if arguments.output.is_absolute() else repo_root / arguments.output
    write_payload(output.resolve(), payload)
    print(f"Wrote {output.resolve()}")
    return 0 if reviews and payload["error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
