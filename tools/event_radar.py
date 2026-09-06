#!/usr/bin/env python3
"""Convert sentiment article evidence into a conservative Event Radar."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVENT_STATES = ("normal", "watch", "important", "critical", "unknown")
_PUNCT = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")
_GENERIC = re.compile(r"一般新闻|市场观点|行业观点|股价|行情|涨停|跌停|资金流向")
_MATERIAL = re.compile(r"公告|政策|关税|监管|处罚|立案|调查|诉讼|事故|并购|收购|解禁|管理层|任命|辞职|客户|审批|许可|披露|控制权|业绩|财报|订单|产能|竞争对手|竞品")
_CRITICAL = re.compile(r"处罚|立案|调查|财务造假|退市|重大事故|控制权|核心客户流失|客户流失|重大诉讼")
_TIER_RANK = {"A": 4, "B": 3, "C": 2, "D": 1}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load(path: Path, default: Any) -> Any:
    if not path.is_file():
        return {"_load_status": "unavailable"} if isinstance(default, dict) else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_load_status": "unavailable"} if isinstance(default, dict) else default


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def _tokens(title: str) -> set[str]:
    text = _PUNCT.sub("", str(title or "")).lower()
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        return {text[index : index + 2] for index in range(max(0, len(text) - 1))}
    return set(text.split())


def _similar(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("url") and left.get("url") == right.get("url"):
        return True
    if left.get("title") == right.get("title"):
        return True
    left_tokens, right_tokens = _tokens(left.get("title", "")), _tokens(right.get("title", ""))
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    # Source classifiers may label the same announcement differently. Keep
    # the lower threshold within one event type, but merge only highly similar
    # titles across event types to avoid joining unrelated company news.
    threshold = 0.34 if left.get("event_type") == right.get("event_type") else 0.55
    return overlap >= threshold


def _articles(company: dict[str, Any]) -> list[dict[str, Any]]:
    news = company.get("news_sentiment") or {}
    candidates = list(news.get("items") or []) + list(news.get("captured_items") or [])
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for article in candidates:
        if not isinstance(article, dict):
            continue
        identity = str(article.get("url") or article.get("title") or "").strip()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(article)
    return result


def _cluster(articles: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    # Retrieval order is not evidence.  Sort before greedy clustering so the
    # same source set produces the same clusters and representative event
    # regardless of provider/list ordering.
    ordered = sorted(
        articles,
        key=lambda article: (
            str(article.get("event_type") or ""),
            str(article.get("title") or ""),
            str(article.get("published_at") or ""),
            str(article.get("url") or ""),
            str(article.get("source_tier") or ""),
        ),
    )
    for article in ordered:
        for cluster in clusters:
            if any(_similar(article, existing) for existing in cluster):
                cluster.append(article)
                break
        else:
            clusters.append([article])
    return clusters


def _evidence(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": article.get("title"),
        "summary": article.get("summary"),
        "publisher": article.get("publisher"),
        "url": article.get("url"),
        "published_at": article.get("published_at"),
        "source_tier": article.get("source_tier") or "unknown",
        "source_tier_label": article.get("source_tier_label"),
        "verification_status": article.get("verification_status"),
        "direction": article.get("direction"),
        "impact": article.get("impact"),
        "relevance": article.get("relevance"),
        "confidence": article.get("confidence"),
    }


def _number(article: dict[str, Any], key: str) -> float:
    try:
        return float(article.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _formal_thesis_event(
    cluster: list[dict[str, Any]],
    *,
    formal_evidence: bool,
    material: bool,
    generic: bool,
) -> bool:
    """Return whether evidence is strong enough for the thesis-drift lane.

    A/B identifies a source that can be trusted, but source authority alone is
    not proof that an announcement changes the investment thesis.  Require a
    material event with either an explicit upstream thesis flag, a sufficiently
    relevant/high-impact assessment, or a critical-risk phrase.  C/D can still
    remain visible as watch/background evidence, but can never pass this gate.
    """
    if not formal_evidence or not material or generic:
        return False
    text = " ".join(
        f"{item.get('title') or ''} {item.get('summary') or ''}"
        for item in cluster
    )
    if _CRITICAL.search(text):
        return True
    return any(
        str(item.get("source_tier") or "").upper() in {"A", "B"}
        and (
            item.get("thesis_relevant") is True
            or (_number(item, "impact") >= 3 and _number(item, "relevance") >= 0.5)
        )
        for item in cluster
    )


def _cluster_record(ticker: str, cluster: list[dict[str, Any]], index: int) -> dict[str, Any]:
    representative = max(cluster, key=lambda item: (_TIER_RANK.get(str(item.get("source_tier") or "").upper(), 0), _number(item, "impact"), str(item.get("published_at") or "")))
    tiers = sorted({str(item.get("source_tier") or "unknown").upper() for item in cluster})
    highest = max(tiers, key=lambda tier: _TIER_RANK.get(tier, 0), default="unknown")
    titles = [str(item.get("title") or "") for item in cluster]
    material = bool(_MATERIAL.search(" ".join(titles)))
    generic = all(_GENERIC.search(title) for title in titles)
    max_impact = max((_number(item, "impact") for item in cluster), default=0)
    # Only A/B evidence can enter the formal thesis-drift channel.  C/D may
    # still raise a visible watch signal, but impact and repost count alone do
    # not promote discussion into a thesis-relevant event.
    formal_evidence = any(str(item.get("source_tier") or "").upper() in {"A", "B"} for item in cluster)
    thesis_relevant = _formal_thesis_event(
        cluster,
        formal_evidence=formal_evidence,
        material=material,
        generic=generic,
    )
    event_text = " ".join(
        f"{item.get('title') or ''} {item.get('summary') or ''}" for item in cluster
    )
    if highest == "A" and _CRITICAL.search(event_text):
        state = "critical"
    elif thesis_relevant:
        state = "important"
    elif max_impact >= 4 or (material and formal_evidence):
        state = "watch"
    elif material and not generic:
        state = "watch"
    else:
        state = "normal"
    digest = hashlib.sha256(f"{ticker}|{representative.get('title')}|{representative.get('published_at')}".encode("utf-8")).hexdigest()[:16]
    return {
        "event_id": f"{ticker}:event:{digest}",
        "event_type": representative.get("event_type") or "一般新闻",
        "summary": representative.get("summary") or representative.get("title"),
        "headline": representative.get("title"),
        "state": state,
        "highest_source_tier": highest,
        "thesis_relevant": thesis_relevant,
        "recommended_action": "run_drift" if thesis_relevant and state in {"important", "critical"} else "monitor" if state == "watch" else "none",
        "evidence_count": len(cluster),
        "evidence": [_evidence(item) for item in cluster],
        "published_at": representative.get("published_at"),
    }


def build_event_radar(repo_root: Path, *, write: bool = True, generated_at: str | None = None) -> dict[str, Any]:
    data_directory = repo_root / "data" / "investment-dashboard"
    sentiment_path = repo_root / "data" / "sentiment" / "latest.json"
    sentiment = _load(sentiment_path, {})
    generated_at = generated_at or _now()
    source_status = (
        sentiment.get("status") or sentiment.get("_load_status") or "unknown"
        if isinstance(sentiment, dict)
        else "unknown"
    )
    companies: list[dict[str, Any]] = []
    for company in sentiment.get("companies", []) if isinstance(sentiment, dict) else []:
        if not isinstance(company, dict) or not company.get("ticker"):
            continue
        ticker = str(company["ticker"]).upper()
        events = [_cluster_record(ticker, group, index) for index, group in enumerate(_cluster(_articles(company)), start=1)]
        rank = {"normal": 0, "watch": 1, "important": 2, "critical": 3}
        highest_state = max((event["state"] for event in events), key=lambda value: rank.get(value, -1), default="normal")
        relevant = any(event["thesis_relevant"] for event in events)
        companies.append({
            "company": company.get("company"),
            "ticker": ticker,
            "market": company.get("market"),
            "state": highest_state,
            "thesis_relevant": relevant,
            "recommended_action": "run_drift" if relevant and highest_state in {"important", "critical"} else "monitor" if highest_state == "watch" else "none",
            "event_count": len(events),
            "events": events,
            "source_status": source_status,
            "last_checked": generated_at,
            "data_cutoff": sentiment.get("data_cutoff"),
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": "data/sentiment/latest.json",
        "source_status": source_status,
        "data_cutoff": sentiment.get("data_cutoff") if isinstance(sentiment, dict) else None,
        "event_states": list(EVENT_STATES),
        "company_count": len(companies),
        "companies": companies,
    }
    if write:
        _write(data_directory / "event_radar.json", payload)
        _write(repo_root / "site" / "data" / "event_radar.json", payload)
    return payload
