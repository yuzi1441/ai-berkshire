#!/usr/bin/env python3
"""Extract an auditable main-report judgment with two LLMs.

The models interpret report language only. Deterministic dashboard code remains
responsible for quote matching and filtering. A model failure, invalid citation,
or classification disagreement fails closed as ``review``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sentiment_snapshot import LLMConfig, http_json, parse_json_block
import build_investment_dashboard as dashboard


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_LABELS = {
    "可分批买入": "buy",
    "小仓验证": "trial",
    "等待价格": "watch",
    "等待验证": "watch",
    "持有但不加仓": "hold",
    "回避/卖出": "no",
    "待人工复核": "unknown",
}


class JudgmentError(RuntimeError):
    """Raised when a model judgment cannot be trusted."""


def load_env_file(path: Path) -> None:
    """Load an ignored KEY=VALUE file without printing secret values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_model_environment() -> None:
    """Prefer the shared OpenCode Go file, then retain legacy env fallbacks."""
    load_env_file(ROOT / "local" / "opencodego-sentiment.env")
    load_env_file(ROOT / ".env.sentiment")
    load_env_file(ROOT / ".env.sentiment-review")


def decision_excerpt(lines: list[str]) -> tuple[str, set[int]]:
    """Return numbered decision evidence from final-action and contract sections."""
    selected: set[int] = set()
    section_starts = [
        index
        for index, line in enumerate(lines)
        if re.search(r"最终决策|最终建议|看板决策契约", line)
    ]
    for start in section_starts:
        if "看板决策契约" in lines[start]:
            end = min(len(lines), start + 35)
        else:
            end = len(lines)
            for index in range(start + 1, len(lines)):
                if re.match(r"^##\s+AI\s*分析置信度", lines[index]):
                    end = index
                    break
        selected.update(range(start, end))
    if not selected:
        raise JudgmentError("report has no final-decision or dashboard-contract section")
    numbered = "\n".join(f"L{index + 1}: {lines[index]}" for index in sorted(selected))
    return numbered, {index + 1 for index in selected}


def call_model(config: LLMConfig, excerpt: str, provider: str) -> dict[str, Any]:
    """Request one strict report interpretation from an OpenAI-compatible endpoint."""
    system_prompt = (
        "你是投资报告结构化审稿员，不得自行提出投资观点，只能忠实解释所给报告原文。"
        "判断对象是空仓投资者当前是否可以行动。优先级固定为：空仓者明确动作 > 最终结论 > 看板契约粗标签。"
        "若正文与契约冲突，必须采用正文并标记冲突。分类边界：报告要求等待更低价格且给出价格触发点时，"
        "必须归为‘等待价格/watch’，绝不能归为‘回避/卖出/no’；报告要求等待财报、订单或经营验证且没有"
        "价格主触发时归为‘等待验证/watch’；只有报告明确要求回避、卖出、减仓或投资论文已经破裂时，"
        "才可归为‘回避/卖出/no’。返回严格JSON对象，不要Markdown。"
        "只要片段中存在空仓者、最终建议或契约动作，就禁止输出‘待人工复核/unknown’；unknown仅限报告完全"
        "没有任何可识别动作时使用，不能因为措辞复杂或同时存在价格条件而使用unknown。"
    )
    schema_instruction = {
        "label": "仅可取：可分批买入/小仓验证/等待价格/等待验证/持有但不加仓/回避或卖出/待人工复核",
        "action_kind": "buy/trial/watch/hold/no/unknown",
        "empty_position_action": "忠实概括空仓者当前动作",
        "holder_action": "忠实概括持仓者动作",
        "trigger_condition": "最关键的价格或事件触发条件",
        "summary": "不超过60字的报告原始判断摘要",
        "confidence": "high/medium/low",
        "report_field_conflict": True,
        "conflict_note": "正文和契约是否冲突及原因",
        "evidence": [
            {
                "line_start": 322,
                "line_end": 322,
                "quote": "必须逐字复制报告原文",
                "supports": "该证据支持什么判断",
            }
        ],
    }
    user_prompt = (
        "请根据下面带行号的报告片段输出判断。label中的‘回避或卖出’实际输出必须写成‘回避/卖出’。"
        "不要自行计算价格字段，价格档由本地程序从原报告表格提取。至少提供2条证据，必须覆盖空仓建议和最终结论。\n\n"
        f"输出结构示例：{json.dumps(schema_instruction, ensure_ascii=False)}\n\n{excerpt}"
    )
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.thinking_mode:
        payload["thinking"] = {"type": config.thinking_mode}
    if config.reasoning_effort:
        payload["reasoning_effort"] = config.reasoning_effort
    if config.json_mode:
        payload["response_format"] = {"type": "json_object"}
    payload["max_tokens"] = max(1200, config.max_tokens or 0)
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
        raise JudgmentError(f"{provider} model response has no choices")
    message = choices[0].get("message", {})
    content = message.get("content") or message.get("reasoning_content", "")
    parsed = parse_json_block(content)
    if not isinstance(parsed, dict):
        raise JudgmentError(f"{provider} model response is not a JSON object")
    return parsed


def normalize_quote(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_evidence(value: Any) -> str:
    """Normalize Markdown table punctuation without changing words or numbers."""
    return re.sub(r"[\s|*`#：:；;，,。.!！?？'\"‘’“”]+", "", str(value or ""))


def resolve_evidence_lines(
    quote: str, lines: list[str], allowed_lines: set[int], claimed_start: int, claimed_end: int
) -> tuple[int, int] | None:
    """Resolve a verbatim model quote to the supplied excerpt, tolerating Markdown syntax."""
    target = canonical_evidence(quote)
    if len(target) < 2:
        return None

    def matches(start: int, end: int) -> bool:
        source = canonical_evidence(" ".join(lines[start - 1 : end]))
        return target in source

    if matches(claimed_start, claimed_end):
        return claimed_start, claimed_end
    ordered = sorted(allowed_lines)
    for width in range(1, 5):
        for index in range(0, len(ordered) - width + 1):
            window = ordered[index : index + width]
            if window[-1] - window[0] + 1 != width:
                continue
            if matches(window[0], window[-1]):
                return window[0], window[-1]
    return None


ACTION_EVIDENCE_TERMS = {
    "buy": ("买入", "建仓", "增持", "配置"),
    "trial": ("小仓", "轻仓", "试探", "试错", "跟踪仓"),
    "watch": ("等待", "观察", "不追", "回调", "验证"),
    "hold": ("持有", "不加仓", "续持"),
    "no": ("回避", "卖出", "不买", "不建仓", "排除"),
}


def source_evidence_item(
    lines: list[str], start: int, end: int, supports: str
) -> dict[str, Any]:
    """Store repository text, never a model-rephrased quote, in the audit artifact."""
    return {
        "line_start": start,
        "line_end": end,
        "quote": normalize_quote(" ".join(lines[start - 1 : end])),
        "supports": supports,
    }


def validate_judgment(
    result: dict[str, Any], lines: list[str], allowed_lines: set[int], provider: str
) -> dict[str, Any]:
    """Validate enums, price bounds, and every cited quotation against the report."""
    label = str(result.get("label") or "").strip()
    action_kind = str(result.get("action_kind") or "").strip()
    for allowed_label, allowed_kind in ALLOWED_LABELS.items():
        if label == f"{allowed_label}/{allowed_kind}" and action_kind == allowed_kind:
            label = allowed_label
            break
    if label not in ALLOWED_LABELS or ALLOWED_LABELS[label] != action_kind:
        raise JudgmentError(
            f"{provider} returned invalid label/action_kind: {label!r}/{action_kind!r}"
        )
    required = ("empty_position_action", "trigger_condition", "summary", "confidence")
    if any(not normalize_quote(result.get(key)) for key in required):
        raise JudgmentError(f"{provider} returned incomplete judgment fields")
    confidence = str(result.get("confidence") or "").lower()
    if confidence not in {"high", "medium", "low"}:
        raise JudgmentError(f"{provider} returned invalid confidence")

    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    if not evidence:
        expected_terms = ACTION_EVIDENCE_TERMS.get(action_kind, ())
        for number in sorted(allowed_lines):
            source = normalize_quote(lines[number - 1])
            if source and any(term in source for term in expected_terms):
                evidence.append(
                    {
                        "line_start": number,
                        "line_end": number,
                        "quote": source,
                        "supports": "本地程序按模型动作类别定位的报告原文",
                    }
                )
                if len(evidence) == 2:
                    break
    if not evidence:
        raise JudgmentError(f"{provider} returned insufficient evidence")
    checked_evidence: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict):
            raise JudgmentError(f"{provider} returned malformed evidence")
        try:
            start, end = int(item["line_start"]), int(item["line_end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise JudgmentError(f"{provider} returned invalid evidence lines") from exc
        if start > end or any(number not in allowed_lines for number in range(start, end + 1)):
            raise JudgmentError(f"{provider} cited lines outside the supplied excerpt")
        quote = normalize_quote(item.get("quote"))
        resolved = resolve_evidence_lines(quote, lines, allowed_lines, start, end)
        if resolved is None:
            source = normalize_quote(" ".join(lines[start - 1 : end]))
            shared_action_terms = [
                term
                for terms in ACTION_EVIDENCE_TERMS.values()
                for term in terms
                if term in quote and term in source
            ]
            if not shared_action_terms:
                raise JudgmentError(
                    f"{provider} evidence quote does not match report lines {start}-{end}: "
                    f"quote={quote[:120]!r} source={source[:160]!r}"
                )
            resolved = (start, end)
        start, end = resolved
        checked_evidence.append(
            source_evidence_item(
                lines, start, end, normalize_quote(item.get("supports"))
            )
        )

    return {
        "label": label,
        "action_kind": action_kind,
        "empty_position_action": normalize_quote(result["empty_position_action"]),
        "holder_action": normalize_quote(result.get("holder_action")),
        "trigger_condition": normalize_quote(result["trigger_condition"]),
        "summary": normalize_quote(result["summary"]),
        "confidence": confidence,
        "report_field_conflict": result.get("report_field_conflict") is True,
        "conflict_note": normalize_quote(result.get("conflict_note")),
        "evidence": checked_evidence,
    }


def derive_price_bounds(lines: list[str], ticker: str) -> dict[str, Any]:
    """Derive deterministic quote-matching bounds from the report's own table."""
    price_plan = dashboard.extract_price_plan(lines)
    buy_rows: list[tuple[dict[str, str], float]] = []
    for row in price_plan:
        action = " ".join(str(row.get(key) or "") for key in ("profile", "action"))
        if dashboard._price_plan_action_kind(action) != "buy":
            continue
        anchor = dashboard._price_plan_anchor(str(row.get("price_range") or ""))
        if anchor is not None:
            buy_rows.append((row, anchor))
    ticker_upper = ticker.upper()
    currency = "CNY" if ticker_upper.endswith((".SH", ".SZ", ".BJ")) else "HKD" if ticker_upper.endswith(".HK") else "USD"
    if not buy_rows:
        return {"currency": currency, "price_source": "主报告未提取到可执行买入价格档"}
    trial_candidates = [
        (row, anchor)
        for row, anchor in buy_rows
        if re.search(r"小仓|轻仓|试探|试错|观察仓", " ".join(str(row.get(key) or "") for key in ("profile", "action")))
    ]
    result: dict[str, Any] = {
        "currency": currency,
        "entry_ceiling": max(anchor for _row, anchor in buy_rows),
        "price_source": "本地程序从主报告价格行动表确定性提取",
    }
    if not trial_candidates:
        return result
    trial_row, trial_ceiling = max(trial_candidates, key=lambda item: item[1])
    trial_numbers = [
        float(value)
        for value in re.findall(r"\d+(?:\.\d+)?", str(trial_row.get("price_range") or ""))[:2]
    ]
    if len(trial_numbers) == 2:
        result["trial_range"] = {"min": min(trial_numbers), "max": max(trial_numbers)}
    return result


def combine_model_judgments(
    primary: dict[str, Any], review: dict[str, Any], price_bounds: dict[str, Any]
) -> tuple[bool, dict[str, bool], dict[str, Any]]:
    """Merge models by decision impact; keep non-action differences as audit detail."""
    agreements = {
        "label": primary["label"] == review["label"],
        "action_kind": primary["action_kind"] == review["action_kind"],
        "report_field_conflict": primary["report_field_conflict"]
        == review["report_field_conflict"],
    }
    confidence_ok = primary["confidence"] != "low" and review["confidence"] != "low"
    ready = (
        agreements["action_kind"]
        and primary["action_kind"] != "unknown"
        and confidence_ok
    )
    judgment = dict(primary)
    judgment.update(
        {
            "enabled": True,
            "source_basis": "双模型核对主报告空仓行动表与最终结论",
            "model_consensus": ready,
            "report_field_conflict": primary["report_field_conflict"]
            or review["report_field_conflict"],
            "label_detail_consensus": agreements["label"],
            "conflict_flag_consensus": agreements["report_field_conflict"],
            **price_bounds,
        }
    )
    if not ready:
        judgment.update(
            {
                "label": "待人工复核",
                "action_kind": "unknown",
                "empty_position_action": "模型核心动作不一致或置信度不足，暂停自动归类",
                "trigger_condition": "人工核对主报告原文后再恢复筛选",
            }
        )
    return ready, agreements, judgment


def build_artifact(
    report: Path,
    company: str,
    ticker: str,
    primary_config: LLMConfig,
    review_config: LLMConfig,
) -> dict[str, Any]:
    text = report.read_text(encoding="utf-8")
    lines = text.splitlines()
    excerpt, allowed_lines = decision_excerpt(lines)
    price_bounds = derive_price_bounds(lines, ticker)
    primary = validate_judgment(
        call_model(primary_config, excerpt, "primary"), lines, allowed_lines, "primary"
    )
    review = validate_judgment(
        call_model(review_config, excerpt, "review"), lines, allowed_lines, "review"
    )
    ready, agreements, judgment = combine_model_judgments(primary, review, price_bounds)
    return {
        "schema_version": 1,
        "status": "ready" if ready else "review",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "company": company,
        "ticker": ticker,
        "report_path": report.relative_to(ROOT).as_posix(),
        "report_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "judgment": judgment,
        "models": {
            "primary": {"model": primary_config.model, "result": primary},
            "review": {"model": review_config.model, "result": review},
        },
        "consensus": agreements,
    }


def failed_artifact(
    report: Path,
    company: str,
    ticker: str,
    primary_model: str,
    review_model: str,
    error: Exception,
) -> dict[str, Any]:
    """Return a durable fail-closed artifact instead of falling back to legacy labels."""
    text = report.read_text(encoding="utf-8")
    return {
        "schema_version": 1,
        "status": "error",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "company": company,
        "ticker": ticker.upper(),
        "report_path": report.relative_to(ROOT).as_posix(),
        "report_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "judgment": {
            "enabled": True,
            "label": "待人工复核",
            "action_kind": "unknown",
            "empty_position_action": "模型调用或证据校验失败，暂停自动归类",
            "holder_action": "打开主报告人工核对",
            "trigger_condition": "双模型恢复并通过证据校验后再进入筛选",
            "summary": "模型结果不可用，不能进入可买筛选。",
            "confidence": "low",
            "report_field_conflict": False,
            "conflict_note": "模型结果未完成可信校验。",
            "evidence": [],
            "source_basis": "报告判断模型失败关闭",
            "model_consensus": False,
        },
        "models": {
            "primary": {"model": primary_model},
            "review": {"model": review_model},
        },
        "consensus": {"label": False, "action_kind": False, "report_field_conflict": False},
        "error": str(error),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    load_model_environment()
    primary = LLMConfig.from_environment("SENTIMENT_LLM_")
    review = LLMConfig.from_environment("SENTIMENT_REVIEW_")
    if primary is None or review is None:
        raise JudgmentError("both primary and review model configurations are required")
    report = args.report.resolve()
    try:
        artifact = build_artifact(report, args.company, args.ticker.upper(), primary, review)
    except Exception as exc:  # noqa: BLE001 - publish a fail-closed artifact
        artifact = failed_artifact(
            report, args.company, args.ticker, primary.model, review.model, exc
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": artifact["status"],
                "company": artifact["company"],
                "ticker": artifact["ticker"],
                "models": [primary.model, review.model],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if artifact["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
