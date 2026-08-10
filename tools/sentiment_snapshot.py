#!/usr/bin/env python3
"""Build an independent A-share/Hong Kong sentiment snapshot.

The snapshot is deliberately separate from the investment dashboard.  It reads
the dashboard's current company universe, but it never rewrites dashboard data,
reports, recommendations, or site assets.

The implementation is suitable for a small VPS: data collection and fallback
scoring use only Python's standard library.  An OpenAI-compatible remote model
can be enabled through environment variables for higher-quality headline
classification; when it is unavailable, deterministic keyword scoring remains
available and is labelled as lower confidence.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time as clock_time, timedelta
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = ROOT / "data" / "investment-dashboard" / "decision_board.json"
DEFAULT_REGISTRY = ROOT / "data" / "report-routing" / "company_registry.json"
DEFAULT_OUTPUT = ROOT / "data" / "sentiment" / "latest.json"
DEFAULT_ARCHIVE_DIR = ROOT / "data" / "sentiment" / "snapshots"

SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
SUPPORTED_MARKETS = {"A股", "港股"}
EASTMONEY_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
ZZSHARE_BASE_URL = "https://api.zizizaizai.com"
USER_AGENT = "ai-berkshire-sentiment-snapshot/1.0"

POSITIVE_TERMS: dict[str, float] = {
    "上调": 1.5,
    "增长": 1.0,
    "大增": 2.0,
    "预增": 1.5,
    "扭亏": 2.0,
    "超预期": 2.0,
    "中标": 1.3,
    "获批": 1.4,
    "回购": 1.0,
    "增持": 1.2,
    "突破": 1.0,
    "创新高": 1.2,
    "签约": 0.8,
    "扩产": 0.7,
    "分红": 0.7,
    "盈利": 0.8,
    "改善": 0.8,
    "利好": 1.2,
    "upgrade": 1.5,
    "beats": 1.8,
    "beat estimates": 1.8,
    "record high": 1.3,
    "approval": 1.3,
    "buyback": 1.0,
}

NEGATIVE_TERMS: dict[str, float] = {
    "下调": 1.5,
    "下降": 1.0,
    "大跌": 1.8,
    "预亏": 1.8,
    "亏损": 1.2,
    "暴雷": 2.5,
    "立案": 2.2,
    "调查": 1.4,
    "处罚": 1.7,
    "罚款": 1.5,
    "诉讼": 1.4,
    "召回": 1.5,
    "减持": 1.2,
    "终止": 1.2,
    "违约": 2.2,
    "退市": 2.5,
    "爆仓": 2.5,
    "裁员": 1.0,
    "风险": 0.6,
    "警示": 1.0,
    "不及预期": 2.0,
    "利空": 1.2,
    "downgrade": 1.5,
    "misses": 1.8,
    "probe": 1.4,
    "lawsuit": 1.4,
    "recall": 1.5,
}

EVENT_TERMS: list[tuple[str, tuple[str, ...]]] = [
    ("监管合规", ("监管", "立案", "调查", "处罚", "罚款", "问询", "退市", "获批")),
    ("业绩财报", ("业绩", "财报", "盈利", "营收", "净利润", "预增", "预亏", "盈警", "盈喜")),
    ("资本动作", ("回购", "增持", "减持", "分红", "配股", "定增", "并购", "收购")),
    ("经营事件", ("中标", "签约", "订单", "扩产", "停产", "召回", "裁员", "新品")),
    ("诉讼风险", ("诉讼", "仲裁", "违约", "索赔")),
    ("行业政策", ("行业", "政策", "关税", "补贴", "价格战")),
]

EVENT_HALF_LIFE_DAYS = {
    "监管合规": 10.0,
    "业绩财报": 10.0,
    "资本动作": 7.0,
    "经营事件": 5.0,
    "诉讼风险": 10.0,
    "行业政策": 5.0,
    "一般新闻": 2.0,
}


class SentimentError(RuntimeError):
    """Raised for a fatal snapshot configuration or input error."""


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for an optional OpenAI-compatible chat endpoint."""

    endpoint: str
    api_key: str
    model: str
    batch_size: int = 20
    workers: int = 4
    thinking_mode: str | None = None
    json_mode: bool = False
    max_tokens: int | None = None

    @classmethod
    def from_environment(cls) -> LLMConfig | None:
        api_key = os.environ.get("SENTIMENT_LLM_API_KEY", "").strip()
        model = os.environ.get("SENTIMENT_LLM_MODEL", "").strip()
        if not api_key or not model:
            return None
        endpoint = os.environ.get(
            "SENTIMENT_LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions"
        ).strip()
        batch_size_text = os.environ.get("SENTIMENT_LLM_BATCH_SIZE", "20").strip()
        try:
            batch_size = min(50, max(1, int(batch_size_text)))
        except ValueError:
            batch_size = 20
        workers_text = os.environ.get("SENTIMENT_LLM_WORKERS", "4").strip()
        try:
            workers = min(12, max(1, int(workers_text)))
        except ValueError:
            workers = 4
        thinking_mode = os.environ.get("SENTIMENT_LLM_THINKING", "").strip().lower()
        if thinking_mode not in {"enabled", "disabled"}:
            thinking_mode = None
        json_mode = os.environ.get("SENTIMENT_LLM_JSON_MODE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        max_tokens_text = os.environ.get("SENTIMENT_LLM_MAX_TOKENS", "").strip()
        try:
            max_tokens = min(8192, max(256, int(max_tokens_text))) if max_tokens_text else None
        except ValueError:
            max_tokens = None
        return cls(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            batch_size=batch_size,
            workers=workers,
            thinking_mode=thinking_mode,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )


def clean_text(value: Any, limit: int | None = None) -> str:
    """Remove markup and normalize whitespace from provider text."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def http_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 20,
    attempts: int = 3,
    encoding: str = "utf-8",
) -> str:
    """Fetch text with bounded retries for transient provider failures."""
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, data=body, headers=request_headers)
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed/configured providers
                return response.read().decode(encoding, errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.6 * (2**attempt))
    raise SentimentError(f"request failed after {attempts} attempts: {url}: {last_error}")


def http_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 20,
    attempts: int = 3,
) -> dict[str, Any]:
    text = http_text(url, headers=headers, body=body, timeout=timeout, attempts=attempts)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise SentimentError(f"provider returned non-object JSON: {url}")
    return payload


def parse_datetime(value: Any) -> datetime | None:
    """Parse common provider timestamps as Asia/Shanghai datetimes."""
    text = clean_text(value)
    if not text:
        return None
    if text.isdigit() and len(text) >= 10:
        try:
            return datetime.fromtimestamp(int(text[:10]), tz=SHANGHAI_TIMEZONE)
        except (OverflowError, OSError, ValueError):
            return None
    normalized = text.replace("/", "-").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SHANGHAI_TIMEZONE)
    return parsed.astimezone(SHANGHAI_TIMEZONE)


def effective_as_of(now: datetime, requested: date | None = None) -> date:
    """Avoid treating an unfinished A/H session as end-of-day data."""
    if requested is not None:
        return requested
    local_now = now.astimezone(SHANGHAI_TIMEZONE)
    cutoff = local_now.date()
    if local_now.time().replace(tzinfo=None) < clock_time(16, 20):
        cutoff -= timedelta(days=1)
    return cutoff


def load_universe(board_path: Path, markets: set[str] | None = None) -> list[dict[str, str]]:
    """Load and de-duplicate the board's A/H company universe by market+ticker."""
    selected_markets = markets or SUPPORTED_MARKETS
    with board_path.open(encoding="utf-8") as handle:
        board = json.load(handle)
    universe: dict[tuple[str, str], dict[str, str]] = {}
    for item in board.get("decisions", []):
        market = clean_text(item.get("market"))
        ticker = clean_text(item.get("ticker")).upper()
        if market not in selected_markets or not ticker:
            continue
        key = (market, ticker)
        universe.setdefault(
            key,
            {
                "company": clean_text(item.get("company")) or ticker,
                "ticker": ticker,
                "market": market,
            },
        )
    return sorted(universe.values(), key=lambda item: (item["market"], item["ticker"]))


def tencent_symbol(ticker: str, market: str) -> str | None:
    raw = ticker.strip().upper()
    if market == "港股" or raw.endswith(".HK"):
        code = raw.removesuffix(".HK")
        return f"hk{code.zfill(5)}" if code.isdigit() else None
    if raw.endswith(".SH"):
        return f"sh{raw.removesuffix('.SH')}"
    if raw.endswith(".SZ"):
        return f"sz{raw.removesuffix('.SZ')}"
    if raw.endswith(".BJ"):
        return f"bj{raw.removesuffix('.BJ')}"
    return None


def fetch_provider_names(universe: list[dict[str, str]]) -> dict[str, str]:
    """Resolve Chinese exchange names in a few lightweight Tencent batches."""
    symbol_to_ticker: dict[str, str] = {}
    for item in universe:
        symbol = tencent_symbol(item["ticker"], item["market"])
        if symbol:
            symbol_to_ticker[symbol] = item["ticker"]
    names: dict[str, str] = {}
    symbols = list(symbol_to_ticker)
    for batch in chunks(symbols, 50):
        payload = http_text(f"{TENCENT_QUOTE_URL}{','.join(batch)}", encoding="gb18030")
        for symbol in batch:
            match = re.search(rf'v_{re.escape(symbol)}="([^"]*)"', payload)
            if not match:
                continue
            fields = match.group(1).split("~")
            if len(fields) > 1 and clean_text(fields[1]):
                names[symbol_to_ticker[symbol]] = clean_text(fields[1])
    return names


def eastmoney_secid(ticker: str, market: str) -> str | None:
    """Convert an A/H ticker to Eastmoney's security identifier."""
    raw = ticker.strip().upper()
    if market == "港股" or raw.endswith(".HK"):
        code = raw.removesuffix(".HK")
        return f"116.{code.zfill(5)}" if code.isdigit() else None
    if raw.endswith(".SH"):
        code = raw.removesuffix(".SH")
        return f"1.{code}" if code.isdigit() else None
    if raw.endswith((".SZ", ".BJ")):
        code = raw.rsplit(".", 1)[0]
        return f"0.{code}" if code.isdigit() else None
    return None


def fetch_provider_industries(
    universe: list[dict[str, str]], workers: int = 6
) -> tuple[dict[str, str], list[str]]:
    """Resolve industries with Eastmoney's batched security-list endpoint."""
    ticker_by_secid = {
        secid: item["ticker"]
        for item in universe
        if (secid := eastmoney_secid(item["ticker"], item["market"]))
    }
    industries: dict[str, str] = {}
    failures = 0
    for secid_batch in chunks(list(ticker_by_secid), 50):
        try:
            query = urlencode(
                {
                    "secids": ",".join(secid_batch),
                    "fields": "f12,f14,f100",
                    "fltt": "2",
                    "invt": "2",
                }
            )
            payload = http_json(f"https://push2.eastmoney.com/api/qt/ulist/get?{query}")
            diff = (payload.get("data") or {}).get("diff") or {}
            rows = diff.values() if isinstance(diff, dict) else diff
            rows_by_code = {clean_text(row.get("f12")): row for row in rows if isinstance(row, dict)}
            for secid in secid_batch:
                code = secid.split(".", 1)[1]
                industry = clean_text((rows_by_code.get(code) or {}).get("f100"))
                if industry:
                    industries[ticker_by_secid[secid]] = industry
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            failures += len(secid_batch)
    warnings = [f"industry lookup failed for {failures} ticker(s)"] if failures else []
    return industries, warnings


def load_registry_names(path: Path) -> dict[str, str]:
    """Build a ticker-to-canonical-name fallback from the routing registry."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        registry = json.load(handle)
    names: dict[str, str] = {}
    for entry in registry.get("companies", []):
        name = clean_text(entry.get("canonical_name"))
        for ticker in entry.get("tickers", []):
            if name:
                names[clean_text(ticker).upper()] = name
    return names


def build_eastmoney_search_url(keyword: str, count: int) -> str:
    search_parameters = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": count,
                "preTag": "",
                "postTag": "",
            }
        },
    }
    query = urlencode(
        {"cb": "sentimentCallback", "param": json.dumps(search_parameters, ensure_ascii=False)}
    )
    return f"{EASTMONEY_SEARCH_URL}?{query}"


def parse_eastmoney_search(
    payload: str,
    *,
    company: str,
    display_name: str,
    ticker: str,
    market: str,
    cutoff: datetime,
    lookback_days: int,
    scope: str = "company",
) -> list[dict[str, Any]]:
    """Parse both known Eastmoney JSONP response shapes."""
    match = re.search(r"^[^(]+\((.*)\)\s*;?\s*$", payload, re.DOTALL)
    if not match:
        raise SentimentError("Eastmoney search returned malformed JSONP")
    parsed = json.loads(match.group(1))
    result = parsed.get("result") or {}
    container = result.get("cmsArticleWebOld", []) if isinstance(result, dict) else []
    if isinstance(container, dict):
        articles = container.get("list", []) or []
    else:
        articles = container or []
    earliest = cutoff - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in articles:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("title"), 240)
        if not title:
            continue
        normalized_title = re.sub(r"\W+", "", title).casefold()
        if normalized_title in seen_titles:
            continue
        published = parse_datetime(item.get("date"))
        if published and (published < earliest or published > cutoff + timedelta(hours=1)):
            continue
        seen_titles.add(normalized_title)
        article_id = hashlib.sha256(f"{ticker}|{normalized_title}".encode()).hexdigest()[:20]
        rows.append(
            {
                "id": article_id,
                "company": company,
                "display_name": display_name,
                "ticker": ticker,
                "market": market,
                "scope": scope,
                "title": title,
                "summary": clean_text(item.get("content") or item.get("digest"), 360),
                "publisher": clean_text(item.get("mediaName") or "东方财富"),
                "url": clean_text(item.get("url")),
                "published_at": published.isoformat() if published else None,
                "source": "Eastmoney search",
            }
        )
    return rows


def fetch_company_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    news_limit: int,
) -> list[dict[str, Any]]:
    # Exchange display names occasionally contain layout spaces (for example
    # "五 粮 液"); removing them materially improves exact company searches.
    query_name = re.sub(r"\s+", "", display_name)
    url = build_eastmoney_search_url(query_name, news_limit)
    payload = http_text(url)
    return parse_eastmoney_search(
        payload,
        company=company["company"],
        display_name=display_name,
        ticker=company["ticker"],
        market=company["market"],
        cutoff=cutoff,
        lookback_days=lookback_days,
        scope="company",
    )


def fetch_industry_news(
    industry: str,
    *,
    cutoff: datetime,
    lookback_days: int,
    news_limit: int,
) -> list[dict[str, Any]]:
    """Fetch one shared news set per primary industry classification."""
    query_name = re.sub(r"\s+", "", industry)
    url = build_eastmoney_search_url(f"{query_name} 行业", news_limit)
    payload = http_text(url)
    return parse_eastmoney_search(
        payload,
        company=f"行业:{industry}",
        display_name=industry,
        ticker=f"industry:{industry}",
        market="行业",
        cutoff=cutoff,
        lookback_days=lookback_days,
        scope="industry",
    )


def detect_event_type(text: str) -> str:
    lowered = text.casefold()
    for event_type, terms in EVENT_TERMS:
        if any(term.casefold() in lowered for term in terms):
            return event_type
    return "一般新闻"


def lexical_score(article: dict[str, Any]) -> dict[str, Any]:
    """Classify a headline deterministically when no remote model is configured."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".casefold()
    positive = sum(weight for term, weight in POSITIVE_TERMS.items() if term.casefold() in text)
    negative = sum(weight for term, weight in NEGATIVE_TERMS.items() if term.casefold() in text)
    raw = positive - negative
    direction = math.tanh(raw / 2.5) if raw else 0.0
    event_type = detect_event_type(text)
    impact = 3 if event_type in {"监管合规", "诉讼风险"} else 2 if event_type != "一般新闻" else 1
    if abs(raw) >= 2:
        impact = min(3, impact + 1)
    company_terms = {
        clean_text(article.get("display_name")).casefold(),
        clean_text(article.get("company")).casefold(),
        re.sub(r"\D", "", clean_text(article.get("ticker"))),
    }
    relevance = 1.0 if any(term and term in text for term in company_terms) else 0.65
    confidence = 0.68 if raw else 0.38
    return {
        "direction": round(direction, 4),
        "impact": impact,
        "relevance": relevance,
        "confidence": confidence,
        "event_type": event_type,
        "scoring_method": "lexicon-v1",
    }


def apply_company_relevance_guard(article: dict[str, Any], score: dict[str, Any]) -> None:
    """Cap company-news relevance when the headline has no company identifier.

    Search feeds occasionally return a roundup article for a neighboring
    company.  A model may still assign it high relevance, so company-name or
    ticker matching is enforced locally before aggregation.  Industry news is
    intentionally exempt because an industry headline need not name every
    constituent company.
    """
    if article.get("scope", "company") != "company":
        return
    text = f"{article.get('title', '')} {article.get('summary', '')}".casefold()
    display_name = clean_text(article.get("display_name")).casefold()
    company_name = clean_text(article.get("company")).casefold()
    ticker_digits = re.sub(r"\D", "", clean_text(article.get("ticker")))
    direct_match = any(
        term and term in text for term in (display_name, company_name, ticker_digits)
    )
    if not direct_match:
        score["relevance"] = min(float(score.get("relevance", 0)), 0.15)
        score["confidence"] = min(float(score.get("confidence", 0)), 0.35)


def parse_json_block(content: str) -> Any:
    stripped = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1)
    start_candidates = [position for position in (stripped.find("["), stripped.find("{")) if position >= 0]
    if start_candidates:
        stripped = stripped[min(start_candidates) :]
    end = max(stripped.rfind("]"), stripped.rfind("}"))
    if end >= 0:
        stripped = stripped[: end + 1]
    return json.loads(stripped)


def score_with_llm(batch: list[dict[str, Any]], config: LLMConfig) -> dict[str, dict[str, Any]]:
    """Score a bounded headline batch using an OpenAI-compatible chat API."""
    compact_articles = [
        {
            "id": item["id"],
            "company": item["display_name"],
            "ticker": item["ticker"],
            "title": item["title"],
            "summary": item.get("summary", "")[:240],
        }
        for item in batch
    ]
    system_prompt = (
        "你是证券新闻分类器，只评估新闻对指定公司或行业未来基本面和风险的增量影响。"
        "返回严格 JSON 对象，格式必须为{\"items\":[...]}; 每项必须含 id、direction(-1到1)、"
        "impact(1到3)、relevance(0到1)、confidence(0到1)、event_type。不要输出投资建议。"
    )
    request_payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(compact_articles, ensure_ascii=False)},
        ],
    }
    if config.thinking_mode:
        request_payload["thinking"] = {"type": config.thinking_mode}
    if config.json_mode:
        request_payload["response_format"] = {"type": "json_object"}
    if config.max_tokens:
        request_payload["max_tokens"] = config.max_tokens
    body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    response = http_json(
        config.endpoint,
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        body=body,
        timeout=60,
        attempts=2,
    )
    choices = response.get("choices") or []
    if not choices:
        raise SentimentError("LLM response has no choices")
    content = choices[0].get("message", {}).get("content", "")
    parsed = parse_json_block(content)
    rows = parsed.get("items", []) if isinstance(parsed, dict) else parsed
    if not isinstance(rows, list):
        raise SentimentError("LLM response is not a JSON array")
    allowed_ids = {item["id"] for item in batch}
    scores: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("id") not in allowed_ids:
            continue
        try:
            direction = clamp(float(row.get("direction", 0)), -1, 1)
            impact = int(clamp(float(row.get("impact", 1)), 1, 3))
            relevance = clamp(float(row.get("relevance", 0)), 0, 1)
            confidence = clamp(float(row.get("confidence", 0)), 0, 1)
        except (TypeError, ValueError):
            continue
        scores[str(row["id"])] = {
            "direction": round(direction, 4),
            "impact": impact,
            "relevance": round(relevance, 4),
            "confidence": round(confidence, 4),
            "event_type": clean_text(row.get("event_type")) or "一般新闻",
            "scoring_method": f"llm:{config.model}",
        }
    return scores


def score_articles(
    articles: list[dict[str, Any]], config: LLMConfig | None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Score all articles, falling back per batch or per missing LLM result."""
    scored = [{**article, **lexical_score(article)} for article in articles]
    warnings: list[str] = []
    if config is None or not scored:
        return scored, warnings
    by_id = {article["id"]: article for article in scored}
    batches = list(chunks(scored, config.batch_size))
    with ThreadPoolExecutor(max_workers=min(config.workers, len(batches))) as executor:
        futures = {executor.submit(score_with_llm, batch, config): batch for batch in batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                llm_scores = future.result()
            except (SentimentError, json.JSONDecodeError, KeyError) as exc:
                warnings.append(f"LLM batch failed; lexicon fallback used: {exc}")
                continue
            for article_id, llm_score in llm_scores.items():
                by_id[article_id].update(llm_score)
            missing_articles = [article for article in batch if article["id"] not in llm_scores]
            # A constrained retry is useful when a model truncates or skips a
            # long response.  Small groups are much less likely to be omitted
            # and keep the fallback reserved for genuine provider failures.
            for retry_batch in chunks(missing_articles, min(5, config.batch_size)):
                try:
                    retry_scores = score_with_llm(retry_batch, config)
                except (SentimentError, json.JSONDecodeError, KeyError):
                    continue
                for article_id, llm_score in retry_scores.items():
                    by_id[article_id].update(llm_score)
            remaining_count = sum(1 for article in missing_articles if article["id"] not in by_id or by_id[article["id"]]["scoring_method"] == "lexicon-v1")
            if remaining_count:
                warnings.append(f"LLM omitted {remaining_count} article(s); lexicon fallback retained")
    for article in by_id.values():
        apply_company_relevance_guard(article, article)
    return list(by_id.values()), warnings


def time_decay(article: dict[str, Any], cutoff: datetime) -> float:
    published = parse_datetime(article.get("published_at"))
    if published is None:
        age_days = 1.0
    else:
        age_days = max(0.0, (cutoff - published).total_seconds() / 86400)
    half_life = EVENT_HALF_LIFE_DAYS.get(article.get("event_type"), 2.0)
    return 0.5 ** (age_days / half_life)


def sentiment_state(score: float) -> str:
    if score <= 30:
        return "显著负面"
    if score < 45:
        return "偏负面"
    if score <= 55:
        return "中性"
    if score < 70:
        return "偏正面"
    return "显著正面"


def aggregate_news(articles: list[dict[str, Any]], cutoff: datetime) -> dict[str, Any]:
    """Aggregate scored headlines with impact, relevance, confidence and decay."""
    relevant_articles = [article for article in articles if float(article.get("relevance", 0)) >= 0.5]
    numerator = 0.0
    denominator = 0.0
    classified_count = 0
    high_impact_negative = 0
    methods: set[str] = set()
    rendered_items: list[dict[str, Any]] = []
    for article in sorted(relevant_articles, key=lambda item: item.get("published_at") or "", reverse=True):
        decay = time_decay(article, cutoff)
        weight = (
            float(article["impact"])
            * float(article["relevance"])
            * float(article["confidence"])
            * decay
        )
        direction = float(article["direction"])
        numerator += direction * weight
        denominator += weight
        if abs(direction) >= 0.15:
            classified_count += 1
        if direction <= -0.35 and int(article["impact"]) >= 3:
            high_impact_negative += 1
        methods.add(str(article["scoring_method"]))
        rendered_items.append(
            {
                "title": article["title"],
                "publisher": article["publisher"],
                "url": article["url"],
                "published_at": article["published_at"],
                "event_type": article["event_type"],
                "direction": article["direction"],
                "impact": article["impact"],
                "relevance": article["relevance"],
                "confidence": article["confidence"],
                "time_weight": round(decay, 4),
                "scoring_method": article["scoring_method"],
            }
        )
    if not relevant_articles or denominator <= 0:
        return {
            "status": "unavailable",
            "score_0_100": None,
            "state": "无数据",
            "confidence": "无数据",
            "article_count": len(articles),
            "relevant_article_count": len(relevant_articles),
            "classified_count": 0,
            "high_impact_negative_count": 0,
            "scoring_methods": [],
            "items": rendered_items,
        }
    normalized = clamp(numerator / denominator, -1, 1)
    score = round(50 + normalized * 50, 2)
    if len(relevant_articles) >= 4 and classified_count >= 2 and any(method.startswith("llm:") for method in methods):
        confidence = "较高"
    elif len(relevant_articles) >= 3 and classified_count >= 1:
        confidence = "中等"
    else:
        confidence = "较低"
    return {
        "status": "ok",
        "score_0_100": score,
        "state": sentiment_state(score),
        "confidence": confidence,
        "article_count": len(articles),
        "relevant_article_count": len(relevant_articles),
        "classified_count": classified_count,
        "high_impact_negative_count": high_impact_negative,
        "scoring_methods": sorted(methods),
        "items": rendered_items,
    }


def zzshare_json(path: str) -> dict[str, Any]:
    token = os.environ.get("ZZSHARE_TOKEN", "").strip()
    headers = {"sdk-key": token} if token else None
    return http_json(f"{ZZSHARE_BASE_URL}/{path.lstrip('/')}", headers=headers)


def safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def market_features(row: dict[str, Any], kline_row: dict[str, Any] | None) -> dict[str, float]:
    up = float(row.get("up_num") or 0)
    down = float(row.get("down_num") or 0)
    uplimit = float(row.get("uplimit_num") or 0)
    downlimit = float(row.get("downlimit_num") or 0)
    gt5 = float(row.get("gt5_num") or 0)
    lt5 = float(row.get("lt5_num") or 0)
    broken = float(row.get("zb_num") or 0)
    index_momentum = 0.0
    if kline_row:
        close = float(kline_row.get("p_close") or 0)
        prior = float(kline_row.get("p_close_pre1d") or 0)
        index_momentum = safe_ratio(close - prior, prior)
    return {
        "breadth_balance": safe_ratio(up - down, up + down),
        "limit_balance": safe_ratio(uplimit - downlimit, uplimit + downlimit),
        "extreme_move_balance": safe_ratio(gt5 - lt5, gt5 + lt5),
        "broken_limit_rate": safe_ratio(broken, uplimit + broken),
        "provider_index_momentum": index_momentum,
    }


def standardized_latest(values: list[float]) -> float:
    if len(values) < 5:
        return values[-1] if values else 0.0
    history = values[:-1][-60:]
    if len(history) < 4:
        return values[-1]
    deviation = statistics.pstdev(history)
    if deviation <= 1e-12:
        return 0.0
    return clamp((values[-1] - statistics.mean(history)) / deviation, -3, 3)


def build_market_sentiment(
    breadth_rows: list[dict[str, Any]],
    kline_rows: list[dict[str, Any]],
    as_of: date,
) -> dict[str, Any]:
    """Build a history-normalized A-share market temperature."""
    kline_by_date = {str(row.get("date")): row for row in kline_rows}
    eligible = []
    for row in breadth_rows:
        row_date = parse_datetime(row.get("date1"))
        if row_date and row_date.date() <= as_of:
            eligible.append(row)
    eligible.sort(key=lambda row: str(row.get("date1")))
    if not eligible:
        return {"status": "unavailable", "score_0_100": None, "state": "无数据"}
    series = []
    for row in eligible:
        date_key = str(row.get("date1", "")).replace("-", "")
        series.append(market_features(row, kline_by_date.get(date_key)))
    feature_z = {name: standardized_latest([item[name] for item in series]) for name in series[-1]}
    composite_z = (
        0.35 * feature_z["breadth_balance"]
        + 0.20 * feature_z["limit_balance"]
        + 0.25 * feature_z["extreme_move_balance"]
        - 0.10 * feature_z["broken_limit_rate"]
        + 0.10 * feature_z["provider_index_momentum"]
    )
    score = round(100 * NormalDist().cdf(composite_z), 2)
    latest = eligible[-1]
    raw_features = series[-1]
    return {
        "status": "ok",
        "source": "zzshare market sentiment API",
        "data_cutoff": str(latest.get("date1")),
        "score_0_100": score,
        "state": sentiment_state(score),
        "history_observations": len(series),
        "raw_metrics": {
            "up_count": latest.get("up_num"),
            "down_count": latest.get("down_num"),
            "limit_up_count": latest.get("uplimit_num"),
            "limit_down_count": latest.get("downlimit_num"),
            "broken_limit_count": latest.get("zb_num"),
            "above_5pct_count": latest.get("gt5_num"),
            "below_minus_5pct_count": latest.get("lt5_num"),
            **{key: round(value, 6) for key, value in raw_features.items()},
        },
        "normalized_components": {key: round(value, 4) for key, value in feature_z.items()},
        "method": "60-observation rolling z-score with normal-CDF mapping",
    }


def fetch_market_context(as_of: date) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    start = as_of - timedelta(days=120)
    start_compact = start.strftime("%Y%m%d")
    end_compact = as_of.strftime("%Y%m%d")
    breadth = zzshare_json(f"v3/sentiment/data?date1={start_compact}&date2={end_compact}").get(
        "data", []
    )
    kline = zzshare_json(
        f"v3/market/sentiment/0/kline?date1={start_compact}&date2={end_compact}"
    ).get("data", [])
    market_sentiment = build_market_sentiment(breadth or [], kline or [], as_of)

    hot_start = (as_of - timedelta(days=7)).strftime("%Y%m%d")
    hot_payload = zzshare_json(
        f"open/sentiment/media/ths2/top?date1={hot_start}&date2={end_compact}"
    )
    hot_rows = [
        row
        for row in (hot_payload.get("data") or [])
        if str(row.get("collect_date", "")) <= as_of.isoformat()
    ]
    latest_hot_date = max((str(row.get("collect_date")) for row in hot_rows), default="")
    hot_by_code: dict[str, dict[str, Any]] = {}
    for row in hot_rows:
        if str(row.get("collect_date")) != latest_hot_date:
            continue
        code = clean_text(row.get("symbol_code"))
        if code:
            hot_by_code[code] = row
    return market_sentiment, hot_by_code


def crowding_snapshot(ticker: str, market: str, hot_by_code: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if market != "A股":
        return {"status": "not_applicable", "attention_score_0_100": None}
    code = ticker.split(".", 1)[0]
    row = hot_by_code.get(code)
    if not row:
        return {"status": "not_in_top_list", "attention_score_0_100": None}
    rank = int(row.get("rank") or 0)
    score = max(1, 101 - rank) if rank else None
    return {
        "status": "ok",
        "source": "zzshare THS popularity ranking",
        "data_cutoff": row.get("collect_date"),
        "attention_score_0_100": score,
        "rank": rank,
        "rank_change": row.get("rank_diff"),
        "price_change_pct": row.get("last_pct"),
        "note": "关注度不是方向性利好，未来融合时只作为拥挤度/过热提示。",
    }


def combined_company_score(
    market: str,
    news: dict[str, Any],
    industry: dict[str, Any] | None,
    market_sentiment: dict[str, Any],
) -> dict[str, Any]:
    news_score = news.get("score_0_100")
    if news_score is None:
        return {"status": "unavailable", "score_0_100": None, "state": "无数据"}
    components: list[tuple[str, float, float]] = [("个股新闻", 0.70 if market == "A股" else 0.80, float(news_score))]
    if industry and industry.get("score_0_100") is not None:
        components.append(("行业新闻", 0.20, float(industry["score_0_100"])))
    if market == "A股" and market_sentiment.get("score_0_100") is not None:
        components.append(("A股市场温度", 0.10, float(market_sentiment["score_0_100"])))
    total_weight = sum(weight for _, weight, _ in components)
    score = round(sum(weight * value for _, weight, value in components) / total_weight, 2)
    method = " + ".join(f"{name}{weight / total_weight:.0%}" for name, weight, _ in components)
    method += "；关注度不计入方向分"
    return {
        "status": "ok",
        "score_0_100": score,
        "state": sentiment_state(score),
        "method": method,
        "preliminary": True,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_snapshot(
    *,
    board_path: Path,
    registry_path: Path,
    as_of: date,
    now: datetime,
    lookback_days: int,
    news_limit: int,
    workers: int,
    company_limit: int | None = None,
    llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    universe = load_universe(board_path)
    if company_limit is not None:
        universe = universe[:company_limit]
    if not universe:
        raise SentimentError("no A-share or Hong Kong companies found in the decision board")

    warnings: list[str] = []
    registry_names = load_registry_names(registry_path)
    try:
        provider_names = fetch_provider_names(universe)
    except SentimentError as exc:
        provider_names = {}
        warnings.append(f"provider name lookup failed: {exc}")
    display_names = {
        item["ticker"]: provider_names.get(item["ticker"])
        or registry_names.get(item["ticker"])
        or item["company"]
        for item in universe
    }
    try:
        provider_industries, industry_warnings = fetch_provider_industries(universe, workers)
        warnings.extend(industry_warnings)
    except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        provider_industries = {}
        warnings.append(f"industry lookup failed: {exc}")
    industries_by_ticker = {
        item["ticker"]: provider_industries.get(item["ticker"], "") for item in universe
    }
    industry_names = sorted({industry for industry in industries_by_ticker.values() if industry})

    try:
        market_sentiment, hot_by_code = fetch_market_context(as_of)
    except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        market_sentiment = {"status": "unavailable", "score_0_100": None, "state": "无数据"}
        hot_by_code = {}
        warnings.append(f"A-share market context failed: {exc}")

    cutoff = datetime.combine(as_of + timedelta(days=1), clock_time.min, SHANGHAI_TIMEZONE)
    articles_by_ticker: dict[str, list[dict[str, Any]]] = {item["ticker"]: [] for item in universe}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 6))) as executor:
        futures = {
            executor.submit(
                fetch_company_news,
                item,
                display_name=display_names[item["ticker"]],
                cutoff=cutoff,
                lookback_days=lookback_days,
                news_limit=news_limit,
            ): item
            for item in universe
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                articles_by_ticker[item["ticker"]] = future.result()
            except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                warnings.append(f"news failed for {item['ticker']}: {exc}")

    industry_articles_by_name: dict[str, list[dict[str, Any]]] = {
        industry: [] for industry in industry_names
    }
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 6))) as executor:
        futures = {
            executor.submit(
                fetch_industry_news,
                industry,
                cutoff=cutoff,
                lookback_days=lookback_days,
                news_limit=news_limit,
            ): industry
            for industry in industry_names
        }
        for future in as_completed(futures):
            industry = futures[future]
            try:
                industry_articles_by_name[industry] = future.result()
            except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                warnings.append(f"industry news failed for {industry}: {exc}")

    all_articles = [article for items in articles_by_ticker.values() for article in items]
    all_articles.extend(article for items in industry_articles_by_name.values() for article in items)
    scored_articles, scoring_warnings = score_articles(all_articles, llm_config)
    warnings.extend(scoring_warnings)
    scored_by_ticker: dict[str, list[dict[str, Any]]] = {item["ticker"]: [] for item in universe}
    scored_by_industry: dict[str, list[dict[str, Any]]] = {industry: [] for industry in industry_names}
    for article in scored_articles:
        if article.get("scope") == "industry":
            scored_by_industry.setdefault(article["display_name"], []).append(article)
        else:
            scored_by_ticker[article["ticker"]].append(article)

    industry_details: dict[str, dict[str, Any]] = {}
    for industry in industry_names:
        full_sentiment = aggregate_news(scored_by_industry[industry], cutoff)
        industry_details[industry] = {
            "industry": industry,
            "company_count": sum(1 for value in industries_by_ticker.values() if value == industry),
            "sentiment": full_sentiment,
        }

    companies = []
    for item in universe:
        news = aggregate_news(scored_by_ticker[item["ticker"]], cutoff)
        crowding = crowding_snapshot(item["ticker"], item["market"], hot_by_code)
        industry = industries_by_ticker[item["ticker"]]
        industry_sentiment = industry_details.get(industry, {}).get("sentiment")
        industry_summary = None
        if industry_sentiment:
            industry_summary = {
                key: value for key, value in industry_sentiment.items() if key != "items"
            }
        companies.append(
            {
                **item,
                "display_name": display_names[item["ticker"]],
                "industry": industry or None,
                "industry_sentiment": industry_summary,
                "combined_sentiment": combined_company_score(
                    item["market"], news, industry_sentiment, market_sentiment
                ),
                "news_sentiment": news,
                "crowding": crowding,
            }
        )

    successful_news = sum(1 for company in companies if company["news_sentiment"]["status"] == "ok")
    successful_industry_news = sum(
        1
        for detail in industry_details.values()
        if detail["sentiment"]["status"] == "ok"
    )
    return {
        "schema_version": 1,
        "generated_at": now.astimezone(SHANGHAI_TIMEZONE).isoformat(),
        "data_cutoff": as_of.isoformat(),
        "scope": ["A股", "港股"],
        "status": "ok" if not warnings else "partial",
        "dashboard_integration": False,
        "universe_source": str(board_path.relative_to(ROOT)) if board_path.is_relative_to(ROOT) else str(board_path),
        "company_count": len(companies),
        "company_news_available_count": successful_news,
        "industry_count": len(industry_names),
        "industry_news_available_count": successful_industry_news,
        "scoring_mode": f"remote-llm:{llm_config.model}+lexicon-fallback" if llm_config else "lexicon-v1",
        "market_sentiment": {"A股": market_sentiment, "港股": {"status": "not_available_in_v1"}},
        "industry_sentiments": industry_details,
        "companies": companies,
        "warnings": warnings,
        "method_notes": [
            "新闻分包含方向、影响强度、相关性、置信度和事件半衰期。",
            "个股综合分默认使用：A股=个股新闻70%+行业新闻20%+市场温度10%；港股=个股新闻80%+行业新闻20%。",
            "A股市场温度使用涨跌家数、涨跌停、极端涨跌、炸板率和情绪指数动量的滚动标准化。",
            "同花顺热度只表示关注/拥挤，不作为方向性利好。",
            "该快照是研究辅助数据，不构成投资建议。",
        ],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--as-of", type=date.fromisoformat, help="end-of-day cutoff (YYYY-MM-DD)")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--news-limit", type=int, default=8)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--company-limit", type=int, help="bounded smoke-test universe")
    parser.add_argument("--no-archive", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    now = datetime.now(tz=SHANGHAI_TIMEZONE)
    as_of = effective_as_of(now, args.as_of)
    if args.lookback_days < 1 or args.news_limit < 1 or args.workers < 1:
        raise SentimentError("lookback-days, news-limit and workers must be positive")
    snapshot = build_snapshot(
        board_path=args.board.resolve(),
        registry_path=args.registry.resolve(),
        as_of=as_of,
        now=now,
        lookback_days=args.lookback_days,
        news_limit=args.news_limit,
        workers=args.workers,
        company_limit=args.company_limit,
        llm_config=LLMConfig.from_environment(),
    )
    write_json(args.output.resolve(), snapshot)
    if not args.no_archive:
        archive_path = args.archive_dir.resolve() / f"{as_of.isoformat()}.json"
        write_json(archive_path, snapshot)
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "data_cutoff": snapshot["data_cutoff"],
                "company_count": snapshot["company_count"],
                "company_news_available_count": snapshot["company_news_available_count"],
                "warning_count": len(snapshot["warnings"]),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SentimentError, OSError, json.JSONDecodeError) as exc:
        print(f"sentiment snapshot failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
