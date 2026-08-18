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
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import decision_consistency_review as consistency  # noqa: E402
import report_judgment  # noqa: E402
from sentiment_snapshot import SentimentError, http_json, parse_json_block  # noqa: E402


MARKET = "A股"
SCAN_SCHEMA_VERSION = 1
DEEP_SCHEMA_VERSION = 1

OPENCODE_GO_BASE = "https://opencode.ai/zen/go/v1"
TRANSPORT_OPENAI_CHAT = "openai_chat"
TRANSPORT_ANTHROPIC_MESSAGES = "anthropic_messages"
TRANSPORT_OPENAI_RESPONSES = "openai_responses"


class OpportunityReviewError(RuntimeError):
    """Raised when an opportunity-review result is unusable."""


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
    "scan_flash": ModelDefaults(
        role="scan_flash",
        model="deepseek-v4-flash",
        transport=TRANSPORT_OPENAI_CHAT,
        endpoint=f"{OPENCODE_GO_BASE}/chat/completions",
        prefix="OPPORTUNITY_SCAN_FLASH_",
    ),
    "scan_qwen": ModelDefaults(
        role="scan_qwen",
        model="qwen3.7-plus",
        transport=TRANSPORT_ANTHROPIC_MESSAGES,
        endpoint=f"{OPENCODE_GO_BASE}/messages",
        prefix="OPPORTUNITY_SCAN_QWEN_",
    ),
    "deep_v4pro": ModelDefaults(
        role="deep_v4pro",
        model="deepseek-v4-pro",
        transport=TRANSPORT_OPENAI_CHAT,
        endpoint=f"{OPENCODE_GO_BASE}/chat/completions",
        prefix="OPPORTUNITY_DEEP_V4PRO_",
    ),
    "deep_luna": ModelDefaults(
        role="deep_luna",
        model="gpt-5.6-luna",
        transport=TRANSPORT_OPENAI_RESPONSES,
        endpoint=f"{OPENCODE_GO_BASE}/responses",
        prefix="OPPORTUNITY_DEEP_LUNA_",
    ),
}

OPPORTUNITY_STATES = {"机会", "条件机会", "暂不构成机会", "证据不足"}
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
    """Read one selected Go model without leaking its token to artifacts."""
    defaults = MODEL_DEFAULTS[role]
    report_judgment.load_model_environment()
    prefix = defaults.prefix
    api_key = (
        os.environ.get(f"{prefix}API_KEY", "").strip()
        or os.environ.get("OPENCODE_GO_API_KEY", "").strip()
    )
    if not api_key:
        raise OpportunityReviewError(
            f"missing API key for {role}; configure {prefix}API_KEY or OPENCODE_GO_API_KEY"
        )
    model = os.environ.get(f"{prefix}MODEL", defaults.model).strip() or defaults.model
    endpoint = os.environ.get(f"{prefix}ENDPOINT", defaults.endpoint).strip() or defaults.endpoint
    timeout_default = 240 if role.startswith("scan_") else 360
    return ModelConfig(
        role=role,
        model=model,
        transport=defaults.transport,
        endpoint=endpoint,
        api_key=api_key,
        max_tokens=parse_integer(
            os.environ.get(f"{prefix}MAX_TOKENS"),
            36000 if defaults.transport == TRANSPORT_ANTHROPIC_MESSAGES else 3200,
            800,
            50000,
        ),
        timeout_seconds=parse_integer(
            os.environ.get(f"{prefix}TIMEOUT"), timeout_default, 30, 600
        ),
        max_retries=parse_integer(os.environ.get(f"{prefix}RETRIES"), 1, 0, 3),
        reasoning_effort=(
            os.environ.get(
                f"{prefix}REASONING_EFFORT",
                # Luna's live Responses endpoint accepts high as its strongest
                # currently supported effort.  Other selected models accept
                # max, while Qwen uses its enabled-thinking budget instead.
                "high" if role == "deep_luna" else "max",
            ).strip().lower()
            or ("high" if role == "deep_luna" else "max")
        ),
        thinking_budget_tokens=parse_integer(
            os.environ.get(f"{prefix}THINKING_BUDGET_TOKENS"), 32000, 1024, 48000
        ),
    )


def report_sha256(repo_root: Path, decision: dict[str, Any]) -> str:
    report_path = repo_root / str(decision.get("report_path") or "")
    if not report_path.is_file():
        raise OpportunityReviewError(f"main report does not exist: {decision.get('report_path')}")
    return hashlib.sha256(report_path.read_bytes()).hexdigest()


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
    return (
        by_ticker(sentiment.get("companies", [])),
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
        "purpose": "识别是否值得投资者现在人工查看，不是买卖指令",
        "inclusion_rule": "任一独立模型判为机会或条件机会，都会进入机会面板",
        "investor_role": "投资者根据完整材料自行决定买、不买或继续观察",
        "mechanical_gate_warning": "本地价格匹配、Checklist、技术面和情绪均是输入事实，不得机械地充当机会否决器",
    }
    encoded = json.dumps(facts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    facts["input_sha256"] = hashlib.sha256(encoded).hexdigest()
    return facts


def review_schema(deep: bool) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "opportunity_state": "仅可取：机会/条件机会/暂不构成机会/证据不足",
        "opportunity_summary": "不超过120字，解释为何值得或不值得投资者现在人工查看；不是买卖指令",
        "supporting_evidence": ["直接来自输入的关键依据，最多4条"],
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


def review_prompts(facts: dict[str, Any], *, deep: bool) -> tuple[str, str]:
    mode = "深度复核" if deep else "全量机会扫描"
    system = (
        f"你是个股研究机会识别员，正在做{mode}。你的职责是理解主报告、当前行情、技术辅助、情绪和Checklist的语义关系，"
        "判断这只股票是否值得投资者现在亲自投入时间复核。你不是投顾，不得下买入、卖出、持有、仓位或目标价指令。"
        "‘机会’只表示出现了值得人工决策的风险收益或信息变化；‘条件机会’表示存在可研究的机会但关键条件仍要由人核实；"
        "‘暂不构成机会’表示输入中没有足够理由把它排到当前人工优先级；‘证据不足’只用于关键输入缺失或互相无法解释。"
        "不得把本地程序的价格匹配、Checklist状态、技术状态或主报告粗标签当作自动否决器；应解释它们各自支持或反驳什么。"
        "这是机会识别而非交易建议：输出中不得出现或复述买入、卖出、持有、建仓、加仓、减仓、仓位、止损、目标价、等待某价再买等动作语言，"
        "即使主报告包含这些词也不要转述。只写为何值得研究、反证是什么、以及投资者应核实哪些事实。"
        "必须只依据输入事实，不得编造外部新闻、财务数据或价格。输出严格JSON，不要Markdown。"
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


def request_json(
    config: ModelConfig,
    *,
    system: str,
    user: str,
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
                    headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
                    body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=config.timeout_seconds,
                    attempts=attempts,
                )
                parsed = parse_json_block(extract_openai_chat_text(response))
                if not isinstance(parsed, dict):
                    raise OpportunityReviewError("chat model did not return a JSON object")
                return parsed, {
                    "requested": f"thinking=enabled; reasoning_effort={requested}",
                    "effective": f"thinking=enabled; reasoning_effort={effective}",
                }
            except Exception as error:  # noqa: BLE001 - try the documented high fallback only
                last_error = error
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
        parsed = parse_json_block(extract_anthropic_text(response))
        if not isinstance(parsed, dict):
            raise OpportunityReviewError("messages model did not return a JSON object")
        reasoning = f"thinking=enabled; budget_tokens={budget}"
        return parsed, {"requested": reasoning, "effective": reasoning}

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
                parsed = parse_json_block(extract_responses_text(response))
                if not isinstance(parsed, dict):
                    raise OpportunityReviewError("Responses model did not return a JSON object")
                return parsed, {
                    "requested": f"reasoning.effort={requested}",
                    "effective": f"reasoning.effort={effective}",
                }
            except Exception as error:  # noqa: BLE001 - try only xhigh/high, never a low fallback
                last_error = error
        raise OpportunityReviewError(f"highest reasoning Responses request failed: {last_error}")

    raise OpportunityReviewError(f"unsupported transport: {config.transport}")


def validate_assessment(result: dict[str, Any], *, deep: bool) -> dict[str, Any]:
    state = clean_text(result.get("opportunity_state"), 30)
    if state not in OPPORTUNITY_STATES:
        raise OpportunityReviewError(f"invalid opportunity_state: {state!r}")
    confidence = clean_text(result.get("confidence"), 20).lower()
    if confidence not in CONFIDENCE:
        raise OpportunityReviewError(f"invalid confidence: {confidence!r}")
    summary = clean_text(result.get("opportunity_summary"), 240)
    if not summary:
        raise OpportunityReviewError("opportunity_summary is empty")
    cleaned = {
        "opportunity_state": state,
        "opportunity_summary": summary,
        "supporting_evidence": [
            clean_text(item, 220)
            for item in (result.get("supporting_evidence") or [])[:4]
            if clean_text(item, 220)
        ],
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
    for key in ("supporting_evidence", "risks_or_counterevidence", "human_questions"):
        if not isinstance(result.get(key, []), list):
            raise OpportunityReviewError(f"{key} must be an array")
    if deep:
        challenge = clean_text(result.get("thesis_challenge"), 300)
        boundary = clean_text(result.get("decision_boundary"), 220)
        if not challenge or not boundary:
            raise OpportunityReviewError("deep review must include thesis_challenge and decision_boundary")
        cleaned["thesis_challenge"] = challenge
        cleaned["decision_boundary"] = boundary
    return cleaned


def run_model(config: ModelConfig, facts: dict[str, Any], *, deep: bool) -> dict[str, Any]:
    started = time.perf_counter()
    system, user = review_prompts(facts, deep=deep)
    try:
        raw, reasoning = request_json(config, system=system, user=user)
        assessment = validate_assessment(raw, deep=deep)
        return {
            "status": "ready",
            "model": config.model,
            "transport": config.transport,
            "generated_at": now_iso(),
            "reasoning": reasoning,
            "assessment": assessment,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as error:  # noqa: BLE001 - preserve a durable per-model error
        return {
            "status": "error",
            "model": config.model,
            "transport": config.transport,
            "generated_at": now_iso(),
            "reasoning": {
                "requested": "highest reasoning only",
                "effective": None,
            },
            "error": clean_text(error, 600),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }


def union_result(models: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ready = [item for item in models.values() if item.get("status") in {"ready", "stale"}]
    opportunities = [
        item
        for item in ready
        if (item.get("assessment") or {}).get("opportunity_state") == "机会"
    ]
    conditional = [
        item
        for item in ready
        if (item.get("assessment") or {}).get("opportunity_state") == "条件机会"
    ]
    positive = opportunities or conditional
    if len(opportunities) >= 2:
        classification = "双模型机会"
    elif len(opportunities) == 1:
        classification = "单模型机会"
    elif conditional:
        classification = "条件机会"
    elif ready:
        classification = "暂不进入机会面板"
    else:
        classification = "待人工复核"
    return {
        "included": bool(positive),
        "classification": classification,
        "supporting_models": [item.get("model") for item in positive if item.get("model")],
        "model_count": len(ready),
        "opportunity_count": len(opportunities),
        "conditional_count": len(conditional),
        "rule": "任一模型判为机会或条件机会即纳入；模型之间互不否决，最终买卖由投资者决定。",
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
        if isinstance(found, dict) and found.get("status") in {"ready", "stale"}:
            return dict(found)
    return None


def scan_one(
    decision: dict[str, Any],
    *,
    repo_root: Path,
    configs: list[ModelConfig],
    sentiment_by_ticker: dict[str, Any],
    intraday_by_ticker: dict[str, Any],
    quote_by_ticker: dict[str, Any],
    previous: dict[str, Any],
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
    models: dict[str, dict[str, Any]] = {}
    # The two independent models see exactly the same frozen evidence snapshot.
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(configs)) as executor:
        futures = {executor.submit(run_model, config, facts, deep=False): config for config in configs}
        for future in concurrent.futures.as_completed(futures):
            config = futures[future]
            try:
                result = future.result()
            except Exception as error:  # defensive; run_model normally handles this
                result = {
                    "status": "error",
                    "model": config.model,
                    "transport": config.transport,
                    "generated_at": now_iso(),
                    "reasoning": {"requested": "highest reasoning only", "effective": None},
                    "error": clean_text(error, 600),
                }
            if result.get("status") == "error":
                fallback = previous_model(previous, ticker, config.model, current_hash)
                if fallback:
                    fallback["status"] = "stale"
                    fallback["stale_reason"] = result.get("error")
                    fallback["last_attempt_at"] = result.get("generated_at")
                    result = fallback
            models[config.model] = result
    return {
        "schema_version": SCAN_SCHEMA_VERSION,
        "status": "ready" if all(item.get("status") == "ready" for item in models.values()) else "partial",
        "company": decision.get("company"),
        "ticker": ticker,
        "market": decision.get("market"),
        "report_path": decision.get("report_path"),
        "report_sha256": current_hash,
        "input_sha256": facts.get("input_sha256"),
        "generated_at": now_iso(),
        "models": models,
        "union": union_result(models),
        "input_snapshot": facts,
    }


def scan_all(
    repo_root: Path,
    *,
    ticker: str | None = None,
    limit: int | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    configs = [model_config("scan_flash"), model_config("scan_qwen")]
    decisions = find_decisions(repo_root, ticker)
    if limit is not None:
        decisions = decisions[: max(0, limit)]
    sentiment, intraday, quotes = snapshot_maps(repo_root)
    prior = previous if isinstance(previous, dict) else {}
    # Each company still gets two independent model calls, but a small bounded
    # company-level pool keeps a full after-close scan practical.  The default
    # means at most six model requests are in flight, avoiding a burst that
    # could exhaust provider concurrency or rate limits.
    workers = parse_integer(os.environ.get("OPPORTUNITY_SCAN_CONCURRENCY"), 3, 1, 6)
    scans: list[dict[str, Any] | None] = [None] * len(decisions)
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
    return {
        "schema_version": SCAN_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "status": "ok" if completed_scans and not errors and not stale else "partial" if completed_scans else "missing",
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
        "company_concurrency": min(workers, len(decisions) or 1),
        "model_result_count": len(model_results),
        "ready_count": ready,
        "stale_count": stale,
        "error_count": errors,
        "inclusion_rule": "任一模型判为机会或条件机会即纳入；模型之间互不否决，最终买卖由投资者决定。",
        "scans": completed_scans,
    }


def deep_review_one(repo_root: Path, ticker: str) -> dict[str, Any]:
    configs = [model_config("deep_v4pro"), model_config("deep_luna")]
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
    # Deep reviews are intentionally serial: a click may consume high-reasoning
    # capacity from two flagship models, and the endpoint has an outer lock.
    models = {config.model: run_model(config, facts, deep=True) for config in configs}
    ready = [item for item in models.values() if item.get("status") == "ready"]
    states = [str((item.get("assessment") or {}).get("opportunity_state") or "") for item in ready]
    return {
        "schema_version": DEEP_SCHEMA_VERSION,
        "status": "ready" if len(ready) == len(configs) else "partial" if ready else "error",
        "company": decision.get("company"),
        "ticker": ticker_upper,
        "market": decision.get("market"),
        "report_path": decision.get("report_path"),
        "report_sha256": report_sha256(repo_root, decision),
        "input_sha256": facts.get("input_sha256"),
        "generated_at": now_iso(),
        "models": models,
        "synthesis": {
            "state_agreement": "一致" if len(set(states)) == 1 and len(states) == 2 else "存在分歧" if len(states) == 2 else "结果不完整",
            "rule": "两份意见并列展示，不合成为买卖结论；最终决定属于投资者。",
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
    payload = scan_all(repo_root, ticker=arguments.ticker, limit=arguments.limit, previous=prior)
    write_json(output, payload)
    print(
        f"Wrote {output} · {payload['ready_count']} ready · {payload['stale_count']} stale · {payload['error_count']} error",
        flush=True,
    )
    return 0 if payload["scan_count"] and payload["ready_count"] else 2


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
    scan = subparsers.add_parser("scan", help="scan all A shares with Flash + Qwen")
    scan.add_argument("--repo-root", type=Path, default=ROOT)
    scan.add_argument("--ticker")
    scan.add_argument("--limit", type=int)
    scan.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "opportunity_scans.json",
    )
    scan.set_defaults(handler=command_scan)
    deep = subparsers.add_parser("deep", help="run V4 Pro + GPT-5.6 Luna for one ticker")
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
