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
from email.utils import parsedate_to_datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = ROOT / "data" / "investment-dashboard" / "decision_board.json"
DEFAULT_REGISTRY = ROOT / "data" / "report-routing" / "company_registry.json"
DEFAULT_OUTPUT = ROOT / "data" / "sentiment" / "latest.json"
DEFAULT_ARCHIVE_DIR = ROOT / "data" / "sentiment" / "snapshots"
DEFAULT_SITE_OUTPUT = ROOT / "site" / "data" / "sentiment.json"
DEFAULT_STATUS_OUTPUT = ROOT / "site" / "data" / "sentiment_status.json"
DEFAULT_PRIMARY_LOOKBACK_DAYS = 7
DEFAULT_FALLBACK_LOOKBACK_DAYS = 30
DEFAULT_LLM_TIMEOUT_SECONDS = 600
DEFAULT_LLM_RETRIES = 4
DEFAULT_LLM_RETRY_BACKOFF_SECONDS = 5.0
DEFAULT_LLM_MISSING_RESULT_RETRIES = 3
DEFAULT_CONTEXT_ANALYSIS_LIMIT = 12
TRANSIENT_HTTP_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
SUPPORTED_MARKETS = {"A股", "港股"}
EASTMONEY_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
EASTMONEY_GUBA_URL = "https://guba.eastmoney.com/list,{symbol}.html"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
BING_NEWS_RSS_URL = "https://www.bing.com/news/search"
BAIDU_NEWS_URL = "http://news.baidu.com/ns"
JINA_READER_PREFIX = "https://r.jina.ai/http://"
SINA_STOCK_NEWS_URL = "https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{symbol}.phtml"
CNINFO_TOPSEARCH_URL = "https://www.cninfo.com.cn/new/information/topSearch/query"
CNINFO_ANNOUNCEMENT_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE = "https://static.cninfo.com.cn"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
ZZSHARE_BASE_URL = "https://api.zizizaizai.com"
USER_AGENT = "ai-berkshire-sentiment-snapshot/1.0"
CNINFO_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.cninfo.com.cn",
    "Referer": "https://www.cninfo.com.cn/",
}

OFFICIAL_SOURCE_TERMS = (
    "巨潮资讯",
    "上海证券交易所",
    "上交所",
    "深圳证券交易所",
    "深交所",
    "北京证券交易所",
    "北交所",
    "香港交易所",
    "港交所",
    "中国证监会",
    "证监会",
    "公司公告",
    "上市公司公告",
    "公司官网",
    "投资者关系",
)
OFFICIAL_SOURCE_DOMAINS = (
    "cninfo.com.cn",
    "sse.com.cn",
    "szse.cn",
    "bse.cn",
    "hkexnews.hk",
)
PROFESSIONAL_SOURCE_TERMS = (
    "财联社",
    "证券时报",
    "中国证券报",
    "上海证券报",
    "第一财经",
    "21世纪",
    "南方财经",
    "每日经济新闻",
    "界面新闻",
    "经济观察",
    "新华财经",
    "人民日报",
    "新华社",
    "央广财经",
    "中国基金报",
    "金融时报",
    "证券日报",
    "中国经营报",
    "澎湃新闻",
)
INDUSTRY_AUTHORITY_SOURCE_TERMS = (
    "国家发展改革委",
    "发改委",
    "工业和信息化部",
    "工信部",
    "商务部",
    "国家能源局",
    "国家统计局",
    "海关总署",
    "国家药监局",
    "国家医保局",
    "市场监管总局",
    "生态环境部",
    "交通运输部",
    "中国汽车流通协会",
    "中国有色金属工业协会",
    "中国钢铁工业协会",
    "中国煤炭工业协会",
    "中国电力企业联合会",
    "中国光伏行业协会",
    "中国半导体行业协会",
)
COMMUNITY_SOURCE_TERMS = (
    "雪球",
    "股吧",
    "微博",
    "微信公众号",
    "论坛",
    "自媒体",
    "抖音",
    "快手",
    "小红书",
)

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
    reasoning_effort: str | None = None
    json_mode: bool = False
    max_tokens: int | None = None
    timeout_seconds: int = DEFAULT_LLM_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_LLM_RETRIES
    retry_backoff_seconds: float = DEFAULT_LLM_RETRY_BACKOFF_SECONDS
    missing_result_retries: int = DEFAULT_LLM_MISSING_RESULT_RETRIES

    @classmethod
    def from_environment(cls, prefix: str = "SENTIMENT_LLM_") -> LLMConfig | None:
        api_key = os.environ.get(f"{prefix}API_KEY", "").strip()
        if not api_key:
            # OpenCode Go uses one workspace key for both model roles. Keep
            # role-specific keys as an override so existing deployments remain
            # compatible while a single OPENCODE_GO_API_KEY is sufficient.
            api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()
        model = os.environ.get(f"{prefix}MODEL", "").strip()
        if not api_key or not model:
            return None
        endpoint = os.environ.get(
            f"{prefix}ENDPOINT", "https://api.openai.com/v1/chat/completions"
        ).strip()
        default_batch_size = "5" if prefix == "SENTIMENT_REVIEW_" else "20"
        batch_size_text = os.environ.get(f"{prefix}BATCH_SIZE", default_batch_size).strip()
        try:
            batch_size = min(50, max(1, int(batch_size_text)))
        except ValueError:
            batch_size = 20
        workers_text = os.environ.get(f"{prefix}WORKERS", "6").strip()
        try:
            workers = min(12, max(1, int(workers_text)))
        except ValueError:
            workers = 4
        thinking_mode = os.environ.get(f"{prefix}THINKING", "disabled").strip().lower()
        if thinking_mode not in {"enabled", "disabled"}:
            thinking_mode = None
        reasoning_effort = os.environ.get(f"{prefix}REASONING_EFFORT", "").strip().lower()
        if reasoning_effort not in {"low", "medium", "high", "max"}:
            reasoning_effort = None
        json_mode = os.environ.get(f"{prefix}JSON_MODE", "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        max_tokens_text = os.environ.get(f"{prefix}MAX_TOKENS", "1800").strip()
        try:
            max_tokens = min(8192, max(256, int(max_tokens_text))) if max_tokens_text else None
        except ValueError:
            max_tokens = None
        timeout_text = os.environ.get(
            f"{prefix}TIMEOUT", str(DEFAULT_LLM_TIMEOUT_SECONDS)
        ).strip()
        try:
            timeout_seconds = min(600, max(30, int(timeout_text)))
        except ValueError:
            timeout_seconds = DEFAULT_LLM_TIMEOUT_SECONDS
        retries_text = os.environ.get(
            f"{prefix}RETRIES", str(DEFAULT_LLM_RETRIES)
        ).strip()
        try:
            max_retries = min(6, max(0, int(retries_text)))
        except ValueError:
            max_retries = DEFAULT_LLM_RETRIES
        backoff_text = os.environ.get(
            f"{prefix}RETRY_BACKOFF", str(DEFAULT_LLM_RETRY_BACKOFF_SECONDS)
        ).strip()
        try:
            retry_backoff_seconds = min(60.0, max(0.5, float(backoff_text)))
        except ValueError:
            retry_backoff_seconds = DEFAULT_LLM_RETRY_BACKOFF_SECONDS
        missing_result_retries_text = os.environ.get(
            f"{prefix}MISSING_RESULT_RETRIES", str(DEFAULT_LLM_MISSING_RESULT_RETRIES)
        ).strip()
        try:
            missing_result_retries = min(6, max(0, int(missing_result_retries_text)))
        except ValueError:
            missing_result_retries = DEFAULT_LLM_MISSING_RESULT_RETRIES
        return cls(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            batch_size=batch_size,
            workers=workers,
            thinking_mode=thinking_mode,
            reasoning_effort=reasoning_effort,
            json_mode=json_mode,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
            missing_result_retries=missing_result_retries,
        )


def clean_text(value: Any, limit: int | None = None) -> str:
    """Remove markup and normalize whitespace from provider text."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def classify_news_source(article: dict[str, Any]) -> dict[str, Any]:
    """Assign a source tier and an explicit scoring permission.

    Eastmoney is treated as a discovery/aggregation channel. A professional
    publisher surfaced through Eastmoney is still secondary evidence; it may
    enter the score, but it is labelled as a single-source secondary report.
    Unknown aggregators and community posts remain visible as auxiliary context
    and never enter the score.
    """
    publisher = clean_text(article.get("publisher"))
    url = clean_text(article.get("url")).casefold()
    publisher_folded = publisher.casefold()
    if any(domain in url for domain in OFFICIAL_SOURCE_DOMAINS) or any(
        term.casefold() in publisher_folded for term in OFFICIAL_SOURCE_TERMS
    ):
        return {
            "source_tier": "A",
            "source_tier_label": "一手披露",
            "score_eligible": True,
            "context_score_eligible": True,
            "context_analysis_eligible": True,
            "verification_status": "official_source",
            "source_via": "official_or_exchange",
        }
    if article.get("scope") == "industry" and any(
        term.casefold() in publisher_folded for term in INDUSTRY_AUTHORITY_SOURCE_TERMS
    ):
        return {
            "source_tier": "A",
            "source_tier_label": "行业权威来源",
            "score_eligible": True,
            "context_score_eligible": True,
            "context_analysis_eligible": True,
            "verification_status": "industry_authority_source",
            "source_via": "industry_authority",
        }
    if any(term.casefold() in publisher_folded for term in PROFESSIONAL_SOURCE_TERMS):
        return {
            "source_tier": "B",
            "source_tier_label": "专业媒体",
            "score_eligible": True,
            "context_score_eligible": True,
            "context_analysis_eligible": True,
            "verification_status": "single_source_secondary",
            "source_via": "eastmoney_aggregator" if "eastmoney.com" in url else "publisher_direct",
        }
    if any(term.casefold() in publisher_folded for term in COMMUNITY_SOURCE_TERMS):
        return {
            "source_tier": "D",
            "source_tier_label": "社区/传闻",
            "score_eligible": False,
            "context_score_eligible": True,
            "context_analysis_eligible": True,
            "verification_status": "unverified",
            "source_via": "community_or_social",
        }
    return {
        "source_tier": "C",
        "source_tier_label": "聚合/其他媒体",
        "score_eligible": False,
        "context_score_eligible": True,
        "context_analysis_eligible": True,
        "verification_status": "single_source_unverified",
        "source_via": "eastmoney_aggregator" if "eastmoney.com" in url else "unknown_channel",
    }


def mark_auxiliary_article(article: dict[str, Any]) -> dict[str, Any]:
    """Keep a non-formal article visible while preserving contextual analysis."""
    exclusion_reason = article.get("score_exclusion_reason")
    if article.get("context_analysis_eligible") is False:
        exclusion_reason = "超过辅助新闻 AI 分析上限：仅展示，不进入模型"
    return {
        **article,
        "direction": None,
        "impact": None,
        "relevance": None,
        "confidence": None,
        "event_type": detect_event_type(f"{article.get('title', '')} {article.get('summary', '')}"),
        "context_score_eligible": bool(article.get("context_score_eligible", True)),
        "scoring_method": "not_scored:analysis_cap"
        if article.get("context_analysis_eligible") is False
        else "not_scored:source_policy",
        "score_exclusion_reason": exclusion_reason
        or f"来源等级{article.get('source_tier', 'C')}：仅作为辅助，不计入正式评分",
    }


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
    retry_backoff_seconds: float = 0.6,
    encoding: str = "utf-8",
) -> str:
    """Fetch text with bounded exponential retries for transient provider failures."""
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, data=body, headers=request_headers)
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed/configured providers
                return response.read().decode(encoding, errors="replace")
        except HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_STATUS_CODES:
                raise SentimentError(
                    f"request failed with non-retryable HTTP {exc.code}: {url}: {exc}"
                ) from exc
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(60.0, retry_backoff_seconds * (2**attempt)))
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(60.0, retry_backoff_seconds * (2**attempt)))
    raise SentimentError(f"request failed after {attempts} attempts: {url}: {last_error}")


def http_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 20,
    attempts: int = 3,
    retry_backoff_seconds: float = 0.6,
) -> dict[str, Any]:
    # A gateway can return HTTP 200 while emitting a truncated JSON envelope.
    # Keep the existing network retry policy, then retry malformed bodies
    # separately before handing the failure back to the batch recovery logic.
    text = http_text(
        url,
        headers=headers,
        body=body,
        timeout=timeout,
        attempts=attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    for parse_attempt in range(max(1, attempts)):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            if parse_attempt + 1 >= max(1, attempts):
                raise SentimentError(
                    f"provider returned malformed JSON after {attempts} parse attempts: {url}"
                ) from exc
            time.sleep(min(60.0, retry_backoff_seconds * (2**parse_attempt)))
            text = http_text(
                url,
                headers=headers,
                body=body,
                timeout=timeout,
                attempts=1,
                retry_backoff_seconds=retry_backoff_seconds,
            )
            continue
        if not isinstance(payload, dict):
            raise SentimentError(f"provider returned non-object JSON: {url}")
        return payload
    raise SentimentError(f"provider returned no JSON payload: {url}")


def http_form_json(
    url: str,
    fields: dict[str, Any],
    *,
    timeout: int = 20,
    attempts: int = 3,
) -> Any:
    """POST form fields to a fixed provider and decode its JSON response."""
    body = urlencode({key: str(value) for key, value in fields.items()}).encode()
    text = http_text(
        url,
        headers=CNINFO_HEADERS,
        body=body,
        timeout=timeout,
        attempts=attempts,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SentimentError(f"provider returned malformed JSON: {url}") from exc


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
    """Resolve industries with batch lookup and per-security recovery."""
    ticker_by_secid = {
        secid: item["ticker"]
        for item in universe
        if (secid := eastmoney_secid(item["ticker"], item["market"]))
    }
    industries: dict[str, str] = {}
    failures: list[str] = []

    def request_rows(secid_batch: list[str]) -> Iterable[dict[str, Any]]:
        query = urlencode(
            {
                "pn": "1",
                "pz": str(max(1, len(secid_batch))),
                "po": "1",
                "np": "1",
                "secids": ",".join(secid_batch),
                "fields": "f12,f14,f100",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
            }
        )
        payload = http_json(f"https://push2.eastmoney.com/api/qt/ulist/get?{query}")
        diff = (payload.get("data") or {}).get("diff") or {}
        rows = diff.values() if isinstance(diff, dict) else diff
        return [row for row in rows if isinstance(row, dict)]

    for secid_batch in chunks(list(ticker_by_secid), 50):
        try:
            rows = request_rows(secid_batch)
            rows_by_code = {clean_text(row.get("f12")): row for row in rows if isinstance(row, dict)}
            for secid in secid_batch:
                code = secid.split(".", 1)[1]
                industry = clean_text((rows_by_code.get(code) or {}).get("f100"))
                if industry:
                    industries[ticker_by_secid[secid]] = industry
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            # A single malformed or rate-limited batch must not erase all
            # industry context. Recover one security at a time and report only
            # the identities that still failed.
            for secid in secid_batch:
                try:
                    rows = request_rows([secid])
                    rows_by_code = {clean_text(row.get("f12")): row for row in rows}
                    code = secid.split(".", 1)[1]
                    industry = clean_text((rows_by_code.get(code) or {}).get("f100"))
                    if industry:
                        industries[ticker_by_secid[secid]] = industry
                    else:
                        failures.append(ticker_by_secid[secid])
                except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                    failures.append(ticker_by_secid[secid])
    warnings = [
        f"industry lookup failed for {len(set(failures))} ticker(s): {', '.join(sorted(set(failures))[:8])}"
    ] if failures else []
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
        row = {
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
        row.update(classify_news_source(row))
        rows.append(row)
    return rows


def fetch_cninfo_stock_identity(ticker: str) -> dict[str, Any] | None:
    """Resolve CNINFO's internal issuer id for an A-share ticker."""
    raw = ticker.strip().upper()
    if not raw.endswith((".SH", ".SZ", ".BJ")):
        return None
    code = raw.rsplit(".", 1)[0]
    payload = http_form_json(
        CNINFO_TOPSEARCH_URL,
        {"keyWord": code, "maxNum": 10, "plate": ""},
    )
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, dict) or clean_text(item.get("code")) != code:
            continue
        if clean_text(item.get("category")) not in {"A股", ""}:
            continue
        org_id = clean_text(item.get("orgId"))
        if org_id:
            return item
    return None


def parse_cninfo_announcements(
    payload: dict[str, Any],
    *,
    company: str,
    display_name: str,
    ticker: str,
    cutoff: datetime,
    lookback_days: int,
    retrieval_window_type: str,
) -> list[dict[str, Any]]:
    """Convert CNINFO's official announcement response to the common article shape."""
    announcements = payload.get("announcements") or []
    if not isinstance(announcements, list):
        return []
    earliest = cutoff - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in announcements:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("announcementTitle") or item.get("shortTitle"), 240)
        announcement_id = clean_text(item.get("announcementId"))
        if not title or not announcement_id or announcement_id in seen_ids:
            continue
        published = parse_datetime(item.get("announcementTime"))
        if published and (published < earliest or published > cutoff + timedelta(hours=1)):
            continue
        adjunct_url = clean_text(item.get("adjunctUrl"))
        if not adjunct_url:
            continue
        seen_ids.add(announcement_id)
        url = f"{CNINFO_STATIC_BASE.rstrip('/')}/{adjunct_url.lstrip('/')}"
        article_id = hashlib.sha256(
            f"{ticker}|cninfo|{announcement_id}".encode()
        ).hexdigest()[:20]
        rows.append(
            {
                "id": article_id,
                "company": company,
                "display_name": display_name,
                "ticker": ticker,
                "market": "A股",
                "scope": "company",
                "title": title,
                "summary": (
                    f"巨潮资讯官方公告，公告编号 {announcement_id}；"
                    "原文为官方披露附件。"
                ),
                "publisher": "巨潮资讯",
                "url": url,
                "published_at": published.isoformat() if published else None,
                "source": "CNINFO official disclosure",
                "source_tier": "A",
                "source_tier_label": "一手披露",
                "score_eligible": True,
                "verification_status": "official_source",
                "source_via": "cninfo_direct",
                "retrieval_window_days": lookback_days,
                "retrieval_window_type": retrieval_window_type,
                "official_announcement_id": announcement_id,
            }
        )
    return rows


def fetch_cninfo_company_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    news_limit: int,
    retrieval_window_type: str,
) -> list[dict[str, Any]]:
    """Fetch first-party A-share disclosures directly from CNINFO."""
    if company.get("market") != "A股":
        return []
    identity = fetch_cninfo_stock_identity(company["ticker"])
    if not identity:
        return []
    end_date = (cutoff - timedelta(microseconds=1)).date()
    start_date = end_date - timedelta(days=lookback_days)
    payload = http_form_json(
        CNINFO_ANNOUNCEMENT_URL,
        {
            "pageNum": 1,
            "pageSize": max(1, news_limit),
            "column": "szse",
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{clean_text(identity.get('code'))},{clean_text(identity.get('orgId'))}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{start_date.isoformat()}~{end_date.isoformat()}",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        },
    )
    if not isinstance(payload, dict):
        raise SentimentError("CNINFO announcement response is not an object")
    return parse_cninfo_announcements(
        payload,
        company=company["company"],
        display_name=display_name,
        ticker=company["ticker"],
        cutoff=cutoff,
        lookback_days=lookback_days,
        retrieval_window_type=retrieval_window_type,
    )


def guba_symbol(ticker: str, market: str) -> str | None:
    """Build the public Eastmoney Guba board symbol for a listed stock."""
    if market != "A股":
        return None
    raw = ticker.strip().upper()
    if not raw.endswith((".SH", ".SZ", ".BJ")):
        return None
    code, exchange = raw.rsplit(".", 1)
    return f"{exchange}{code.zfill(6)}"


def parse_guba_html(
    payload: str,
    *,
    company: str,
    display_name: str,
    ticker: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Parse the public article_list embedded in an Eastmoney Guba page."""
    match = re.search(r"var\s+article_list\s*=\s*(\{.*?\});", payload, re.DOTALL)
    if not match:
        raise SentimentError("Eastmoney Guba page has no article_list payload")
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise SentimentError("Eastmoney Guba article_list is malformed JSON") from exc
    articles = parsed.get("re") or []
    if not isinstance(articles, list):
        return []
    earliest = cutoff - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in articles:
        if not isinstance(item, dict):
            continue
        post_id = clean_text(item.get("post_id"))
        title = clean_text(item.get("post_title"), 240)
        if not post_id or not title or post_id in seen_ids:
            continue
        published = parse_datetime(
            item.get("post_publish_time") or item.get("post_display_time")
        )
        if published and (published < earliest or published > cutoff + timedelta(hours=1)):
            continue
        seen_ids.add(post_id)
        post_type = clean_text(item.get("post_type")) or "0"
        nickname = clean_text(item.get("user_nickname")) or "匿名用户"
        is_user_post = post_type == "0"
        source_tier = "D" if is_user_post else "C"
        source_label = "社区讨论" if is_user_post else "平台资讯/自媒体"
        source_status = "community_unverified" if is_user_post else "platform_unverified"
        url = f"https://guba.eastmoney.com/news,{ticker.split('.', 1)[0]},{post_id}.html"
        read_count = int(item.get("post_click_count") or 0)
        comment_count = int(item.get("post_comment_count") or 0)
        rows.append(
            {
                "id": hashlib.sha256(
                    f"{ticker}|guba|{post_id}".encode()
                ).hexdigest()[:20],
                "company": company,
                "display_name": display_name,
                "ticker": ticker,
                "market": "A股",
                "scope": "company",
                "title": title,
                "summary": (
                    f"东方财富股吧帖子；作者：{nickname}；阅读：{read_count}；"
                    f"评论：{comment_count}。社区内容未经核验。"
                ),
                "publisher": f"东方财富股吧·{nickname}",
                "url": url,
                "published_at": published.isoformat() if published else None,
                "source": "Eastmoney Guba public board",
                "source_tier": source_tier,
                "source_tier_label": source_label,
                "score_eligible": False,
                "verification_status": source_status,
                "source_via": "eastmoney_guba",
                "retrieval_window_days": lookback_days,
                "retrieval_window_type": retrieval_window_type,
                "guba_post_id": post_id,
                "guba_post_type": post_type,
            }
        )
        if len(rows) >= max(1, limit):
            break
    return rows


def fetch_guba_company_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Fetch low-confidence community signals from a public A-share board."""
    symbol = guba_symbol(company["ticker"], company.get("market", ""))
    if not symbol:
        return []
    payload = http_text(
        EASTMONEY_GUBA_URL.format(symbol=symbol),
        headers={"Referer": "https://guba.eastmoney.com/"},
    )
    return parse_guba_html(
        payload,
        company=company["company"],
        display_name=display_name,
        ticker=company["ticker"],
        cutoff=cutoff,
        lookback_days=lookback_days,
        limit=limit,
        retrieval_window_type=retrieval_window_type,
    )


def sina_symbol(ticker: str, market: str) -> str | None:
    """Build Sina Finance's public stock-news symbol for an A-share."""
    if market != "A股":
        return None
    raw = ticker.strip().upper()
    if raw.endswith(".SH"):
        return f"sh{raw.removesuffix('.SH').zfill(6)}"
    if raw.endswith(".SZ"):
        return f"sz{raw.removesuffix('.SZ').zfill(6)}"
    if raw.endswith(".BJ"):
        return f"bj{raw.removesuffix('.BJ').zfill(6)}"
    return None


def parse_sina_stock_news(
    payload: str,
    *,
    company: str,
    display_name: str,
    ticker: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Parse Sina's server-rendered individual-stock news list as C-level context."""
    block_match = re.search(
        r'<div[^>]+class=["\']tagmain["\'][^>]*>.*?'
        r'<div[^>]+class=["\']datelist["\'][^>]*>.*?'
        r'<ul>(.*?)</ul>',
        payload,
        re.IGNORECASE | re.DOTALL,
    )
    if not block_match:
        return []
    block = html.unescape(block_match.group(1)).replace("&nbsp;", " ")
    item_pattern = re.compile(
        r"(?P<date>\d{4}[-/]\d{2}[-/]\d{2})\s*"
        r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s*"
        r"<a\b[^>]*href=[\"'](?P<url>[^\"']+)[\"'][^>]*>"
        r"(?P<title>.*?)</a>",
        re.IGNORECASE | re.DOTALL,
    )
    earliest = cutoff - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in item_pattern.finditer(block):
        title = clean_text(match.group("title"), 240)
        url = clean_text(match.group("url"))
        if not title or not url:
            continue
        published = parse_datetime(f"{match.group('date')} {match.group('time')}")
        if published and (published < earliest or published > cutoff + timedelta(hours=1)):
            continue
        key = url or title
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": hashlib.sha256(f"{ticker}|sina|{key}".encode()).hexdigest()[:20],
                "company": company,
                "display_name": display_name,
                "ticker": ticker,
                "market": "A股",
                "scope": "company",
                "title": title,
                "summary": "新浪财经个股资讯页面收录；仅作辅助线索，未对内容进行一手核验。",
                "publisher": "新浪财经",
                "url": url,
                "published_at": published.isoformat() if published else None,
                "source": "Sina Finance individual-stock news",
                "source_tier": "C",
                "source_tier_label": "新浪财经辅助资讯",
                "score_eligible": False,
                "verification_status": "publisher_auxiliary_unverified",
                "source_via": "sina_stock_news",
                "retrieval_window_days": lookback_days,
                "retrieval_window_type": retrieval_window_type,
            }
        )
        if len(rows) >= max(1, limit):
            break
    return rows


def fetch_sina_company_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Fetch Sina's public individual-stock news page without model scoring."""
    symbol = sina_symbol(company["ticker"], company.get("market", ""))
    if not symbol:
        return []
    payload = http_text(
        SINA_STOCK_NEWS_URL.format(symbol=symbol),
        headers={"Referer": "https://finance.sina.com.cn/"},
        timeout=30,
        encoding="gb18030",
    )
    return parse_sina_stock_news(
        payload,
        company=company["company"],
        display_name=display_name,
        ticker=company["ticker"],
        cutoff=cutoff,
        lookback_days=lookback_days,
        limit=limit,
        retrieval_window_type=retrieval_window_type,
    )


def baidu_news_search_url(query: str) -> str:
    return f"https://news.baidu.com/ns?{urlencode({'word': query, 'tn': 'news', 'from': 'news', 'cl': '2', 'rn': '20', 'ct': '1'})}"


def parse_relative_reader_datetime(value: Any, cutoff: datetime) -> datetime | None:
    """Parse absolute or relative dates emitted by a text-reader proxy."""
    text = clean_text(value)
    if not text:
        return None
    absolute = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}(?:\s+\d{1,2}:\d{2})?", text)
    if absolute:
        parsed = parse_datetime(absolute.group(0))
        if parsed:
            return parsed
    if "刚刚" in text:
        return cutoff
    relative_units = (("分钟", "minutes"), ("小时", "hours"), ("天", "days"))
    for unit, keyword in relative_units:
        match = re.search(rf"(\d+)\s*{unit}前", text)
        if match:
            return cutoff - timedelta(**{keyword: int(match.group(1))})
    return None


def parse_baidu_reader_news(
    payload: str,
    *,
    company: str,
    display_name: str,
    ticker: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    source_page_url: str,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Parse Baidu News markdown returned by a read-only text proxy."""
    earliest = cutoff - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^\s*###\s+\[([^\]]+)\]\((https?://[^)]+)\)\s*(.*)$")
    for line in payload.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        title = clean_text(match.group(1), 240)
        url = clean_text(match.group(2))
        metadata = clean_text(match.group(3), 480)
        if not title or not url:
            continue
        published = parse_relative_reader_datetime(metadata, cutoff)
        if published and (published < earliest or published > cutoff + timedelta(hours=1)):
            continue
        if url in seen:
            continue
        seen.add(url)
        source_links = re.findall(r"\[([^\]]+)\]\(https?://[^)]+\)", metadata)
        publisher = clean_text(source_links[-1]) if source_links else "百度资讯搜索"
        rows.append(
            {
                "id": hashlib.sha256(f"{ticker}|baidu|{url}".encode()).hexdigest()[:20],
                "company": company,
                "display_name": display_name,
                "ticker": ticker,
                "market": "A股",
                "scope": "company",
                "title": title,
                "summary": metadata or "百度资讯搜索结果；仅作辅助线索，未对内容进行一手核验。",
                "publisher": publisher,
                "url": url,
                "published_at": published.isoformat() if published else None,
                "source": "Baidu News search",
                "source_tier": "C",
                "source_tier_label": "百度资讯辅助搜索",
                "score_eligible": False,
                "verification_status": "reader_proxy_unverified",
                "source_via": "baidu_news_reader_proxy",
                "source_page_url": source_page_url,
                "retrieval_proxy": "r.jina.ai",
                "retrieval_window_days": lookback_days,
                "retrieval_window_type": retrieval_window_type,
            }
        )
        if len(rows) >= max(1, limit):
            break
    return rows


def fetch_baidu_company_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Fetch Baidu News through a read-only text proxy when direct access is challenged."""
    if company.get("market") != "A股":
        return []
    code = company["ticker"].split(".", 1)[0]
    source_page_url = baidu_news_search_url(f'"{display_name}" {code}')
    reader_url = f"{JINA_READER_PREFIX}{source_page_url.removeprefix('https://')}"
    payload = http_text(
        reader_url,
        headers={"Accept": "text/plain"},
        timeout=45,
        attempts=2,
    )
    return parse_baidu_reader_news(
        payload,
        company=company["company"],
        display_name=display_name,
        ticker=company["ticker"],
        cutoff=cutoff,
        lookback_days=lookback_days,
        limit=limit,
        source_page_url=source_page_url,
        retrieval_window_type=retrieval_window_type,
    )


def rss_child_text(item: ElementTree.Element, child_name: str) -> str:
    """Read an RSS child while tolerating provider-specific XML namespaces."""
    for child in list(item):
        if child.tag.rsplit("}", 1)[-1] == child_name:
            return clean_text(child.text)
    return ""


def parse_rss_datetime(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return parse_datetime(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=SHANGHAI_TIMEZONE)
    return parsed.astimezone(SHANGHAI_TIMEZONE)


def parse_rss_news(
    payload: str,
    *,
    company: str,
    display_name: str,
    ticker: str,
    cutoff: datetime,
    lookback_days: int,
    source_via: str,
    channel_name: str,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Parse Google/Bing News RSS items as unscored C-level context."""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise SentimentError(f"{channel_name} RSS is malformed XML") from exc
    earliest = cutoff - timedelta(days=lookback_days)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] != "item":
            continue
        title = rss_child_text(item, "title")
        link = rss_child_text(item, "link")
        if not title or not link:
            continue
        published = parse_rss_datetime(rss_child_text(item, "pubDate"))
        if published and (published < earliest or published > cutoff + timedelta(hours=1)):
            continue
        key = link or title
        if key in seen:
            continue
        seen.add(key)
        publisher = rss_child_text(item, "source") or channel_name
        summary = rss_child_text(item, "description")
        rows.append(
            {
                "id": hashlib.sha256(
                    f"{ticker}|{source_via}|{key}".encode()
                ).hexdigest()[:20],
                "company": company,
                "display_name": display_name,
                "ticker": ticker,
                "market": "A股",
                "scope": "company",
                "title": title,
                "summary": clean_text(summary, 360),
                "publisher": publisher,
                "url": link,
                "published_at": published.isoformat() if published else None,
                "source": f"{channel_name} RSS",
                "source_tier": "C",
                "source_tier_label": "RSS聚合资讯",
                "score_eligible": False,
                "verification_status": "rss_aggregator_unverified",
                "source_via": source_via,
                "retrieval_window_days": lookback_days,
                "retrieval_window_type": retrieval_window_type,
                "rss_channel": channel_name,
            }
        )
        if len(rows) >= max(1, limit):
            break
    return rows


def rss_search_url(provider: str, query: str) -> str:
    encoded = quote(query)
    if provider == "google":
        return (
            f"{GOOGLE_NEWS_RSS_URL}?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        )
    return f"{BING_NEWS_RSS_URL}?q={encoded}&format=rss&setlang=zh-CN"


def fetch_rss_company_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Fetch multi-provider RSS search results for C-level auxiliary context."""
    if company.get("market") != "A股":
        return []
    code = company["ticker"].split(".", 1)[0]
    query = f'"{display_name}" {code}'
    providers = (
        ("google", "Google News"),
        ("bing", "Bing News"),
    )
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for provider, channel_name in providers:
        try:
            payload = http_text(
                rss_search_url(provider, query),
                headers={"Accept": "application/rss+xml,application/xml,text/xml"},
            )
            rows.extend(
                parse_rss_news(
                    payload,
                    company=company["company"],
                    display_name=display_name,
                    ticker=company["ticker"],
                    cutoff=cutoff,
                    lookback_days=lookback_days,
                    source_via=f"{provider}_news_rss",
                    channel_name=channel_name,
                    limit=limit,
                    retrieval_window_type=retrieval_window_type,
                )
            )
        except (SentimentError, HTTPError, URLError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{channel_name}: {exc}")
    if not rows and errors:
        raise SentimentError("; ".join(errors))
    return rows


def fetch_xueqiu_indexed_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    limit: int,
    retrieval_window_type: str = "recent",
) -> list[dict[str, Any]]:
    """Collect publicly indexed Xueqiu pages without bypassing Xueqiu's WAF."""
    if company.get("market") != "A股":
        return []
    code = company["ticker"].split(".", 1)[0]
    query = f'"{display_name}" {code} site:xueqiu.com'
    payload = http_text(
        rss_search_url("google", query),
        headers={"Accept": "application/rss+xml,application/xml,text/xml"},
    )
    rows = parse_rss_news(
        payload,
        company=company["company"],
        display_name=display_name,
        ticker=company["ticker"],
        cutoff=cutoff,
        lookback_days=lookback_days,
        source_via="xueqiu_google_index",
        channel_name="雪球公开索引",
        limit=limit,
        retrieval_window_type=retrieval_window_type,
    )
    for row in rows:
        row.update(
            {
                "source": "Google News indexed Xueqiu pages",
                "source_tier": "D",
                "source_tier_label": "雪球社区/公开索引",
                "score_eligible": False,
                "verification_status": "indexed_community_unverified",
                "source_via": "xueqiu_google_index",
                "source_page_url": "https://xueqiu.com/",
                "retrieval_proxy": "Google News RSS",
            }
        )
    return rows


def source_priority(article: dict[str, Any]) -> int:
    """Prefer direct official disclosures when feeds contain the same title."""
    if article.get("source_via") == "cninfo_direct":
        return 5
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(article.get("source_tier"), 0)


def merge_news_sources(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate identical headlines across official and discovery feeds."""
    by_title: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for article in articles:
        title_key = re.sub(r"\W+", "", clean_text(article.get("title"))).casefold()
        key = title_key or clean_text(article.get("id"))
        if not key:
            continue
        current = by_title.get(key)
        if current is None:
            by_title[key] = article
            order.append(key)
            continue
        if source_priority(article) > source_priority(current):
            by_title[key] = article
    return [by_title[key] for key in order]


def cap_auxiliary_news(
    articles: list[dict[str, Any]],
    auxiliary_news_limit: int,
    context_analysis_limit: int = DEFAULT_CONTEXT_ANALYSIS_LIMIT,
) -> list[dict[str, Any]]:
    """Keep scoring intact while giving every auxiliary channel coverage.

    The displayed auxiliary pool may be larger than the model pool.  Mark only
    the newest round-robin subset for contextual AI analysis so a full scan
    cannot multiply remote-model cost by every low-quality feed item.
    """
    scoreable = [article for article in articles if article.get("score_eligible", True)]
    auxiliary = [article for article in articles if not article.get("score_eligible", True)]
    limit = max(1, auxiliary_news_limit)
    by_channel: dict[str, list[dict[str, Any]]] = {}
    for article in auxiliary:
        channel = clean_text(article.get("source_via")) or "unknown_channel"
        by_channel.setdefault(channel, []).append(article)
    for channel_rows in by_channel.values():
        channel_rows.sort(key=lambda item: item.get("published_at") or "", reverse=True)

    # Round-robin selection prevents a fast, high-volume community feed from
    # consuming the whole auxiliary budget and hiding Baidu/Sina/RSS signals.
    selected: list[dict[str, Any]] = []
    channels = sorted(by_channel)
    while len(selected) < limit and channels:
        next_channels: list[str] = []
        for channel in channels:
            channel_rows = by_channel[channel]
            if channel_rows:
                selected.append(channel_rows.pop(0))
                if len(selected) >= limit:
                    break
            if channel_rows:
                next_channels.append(channel)
        channels = next_channels
    selected.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    analysis_limit = max(0, context_analysis_limit)
    for index, article in enumerate(selected):
        article["context_analysis_eligible"] = index < analysis_limit
        article["context_analysis_rank"] = index + 1
    return scoreable + selected


def fetch_company_news_result(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    news_limit: int,
    auxiliary_news_limit: int = 60,
    context_analysis_limit: int = DEFAULT_CONTEXT_ANALYSIS_LIMIT,
    rss_news_limit: int = 20,
    fallback_lookback_days: int = DEFAULT_FALLBACK_LOOKBACK_DAYS,
) -> tuple[list[dict[str, Any]], list[str]]:
    # Exchange display names occasionally contain layout spaces (for example
    # "五 粮 液"); removing them materially improves exact company searches.
    query_name = re.sub(r"\s+", "", display_name)

    def fetch_window(
        window_days: int, window_type: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        rows: list[dict[str, Any]] = []
        source_errors: list[str] = []
        try:
            url = build_eastmoney_search_url(query_name, news_limit)
            payload = http_text(url)
            rows.extend(
                parse_eastmoney_search(
                    payload,
                    company=company["company"],
                    display_name=display_name,
                    ticker=company["ticker"],
                    market=company["market"],
                    cutoff=cutoff,
                    lookback_days=window_days,
                    scope="company",
                )
            )
            if auxiliary_news_limit > news_limit:
                auxiliary_payload = http_text(
                    build_eastmoney_search_url(query_name, auxiliary_news_limit)
                )
                auxiliary_rows = parse_eastmoney_search(
                    auxiliary_payload,
                    company=company["company"],
                    display_name=display_name,
                    ticker=company["ticker"],
                    market=company["market"],
                    cutoff=cutoff,
                    lookback_days=window_days,
                    scope="company",
                )
                rows.extend(
                    row for row in auxiliary_rows if not row.get("score_eligible", True)
                )
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            source_errors.append(f"Eastmoney: {exc}")
        for row in rows:
            row["retrieval_window_days"] = window_days
            row["retrieval_window_type"] = window_type
        try:
            rows.extend(
                fetch_cninfo_company_news(
                    company,
                    display_name=display_name,
                    cutoff=cutoff,
                    lookback_days=window_days,
                    news_limit=news_limit,
                    retrieval_window_type=window_type,
                )
            )
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if company.get("market") == "A股":
                source_errors.append(f"CNINFO: {exc}")
        try:
            rows.extend(
                fetch_sina_company_news(
                    company,
                    display_name=display_name,
                    cutoff=cutoff,
                    lookback_days=window_days,
                    limit=auxiliary_news_limit,
                    retrieval_window_type=window_type,
                )
            )
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if company.get("market") == "A股":
                source_errors.append(f"Sina Finance: {exc}")
        try:
            rows.extend(
                fetch_baidu_company_news(
                    company,
                    display_name=display_name,
                    cutoff=cutoff,
                    lookback_days=window_days,
                    limit=auxiliary_news_limit,
                    retrieval_window_type=window_type,
                )
            )
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if company.get("market") == "A股":
                source_errors.append(f"Baidu News: {exc}")
        try:
            rows.extend(
                fetch_guba_company_news(
                    company,
                    display_name=display_name,
                    cutoff=cutoff,
                    lookback_days=window_days,
                    limit=auxiliary_news_limit,
                    retrieval_window_type=window_type,
                )
            )
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if company.get("market") == "A股":
                source_errors.append(f"Eastmoney Guba: {exc}")
        try:
            rows.extend(
                fetch_rss_company_news(
                    company,
                    display_name=display_name,
                    cutoff=cutoff,
                    lookback_days=window_days,
                    limit=rss_news_limit,
                    retrieval_window_type=window_type,
                )
            )
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if company.get("market") == "A股":
                source_errors.append(f"RSS: {exc}")
        try:
            rows.extend(
                fetch_xueqiu_indexed_news(
                    company,
                    display_name=display_name,
                    cutoff=cutoff,
                    lookback_days=window_days,
                    limit=rss_news_limit,
                    retrieval_window_type=window_type,
                )
            )
        except (SentimentError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if company.get("market") == "A股":
                source_errors.append(f"Xueqiu indexed search: {exc}")
        return cap_auxiliary_news(
            merge_news_sources(rows),
            auxiliary_news_limit,
            context_analysis_limit,
        ), source_errors

    rows, source_errors = fetch_window(lookback_days, "recent")
    if rows or fallback_lookback_days <= lookback_days:
        return rows, source_errors
    # A wider second query is only made when the primary window is empty. This
    # keeps normal runs cheap while still finding the latest usable headline.
    fallback_rows, fallback_errors = fetch_window(fallback_lookback_days, "fallback")
    return fallback_rows, source_errors + fallback_errors


def fetch_company_news(
    company: dict[str, str],
    *,
    display_name: str,
    cutoff: datetime,
    lookback_days: int,
    news_limit: int,
    auxiliary_news_limit: int = 60,
    context_analysis_limit: int = DEFAULT_CONTEXT_ANALYSIS_LIMIT,
    rss_news_limit: int = 20,
    fallback_lookback_days: int = DEFAULT_FALLBACK_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    """Fetch company news while preserving the legacy list-returning API."""
    rows, _ = fetch_company_news_result(
        company,
        display_name=display_name,
        cutoff=cutoff,
        lookback_days=lookback_days,
        news_limit=news_limit,
        auxiliary_news_limit=auxiliary_news_limit,
        context_analysis_limit=context_analysis_limit,
        rss_news_limit=rss_news_limit,
        fallback_lookback_days=fallback_lookback_days,
    )
    return rows


def fetch_industry_news(
    industry: str,
    *,
    cutoff: datetime,
    lookback_days: int,
    news_limit: int,
    auxiliary_news_limit: int = 60,
    context_analysis_limit: int = DEFAULT_CONTEXT_ANALYSIS_LIMIT,
    fallback_lookback_days: int = DEFAULT_FALLBACK_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    """Fetch one shared news set per primary industry classification."""
    query_name = re.sub(r"\s+", "", industry)
    def fetch_window(window_days: int, window_type: str) -> list[dict[str, Any]]:
        url = build_eastmoney_search_url(f"{query_name} 行业", news_limit)
        payload = http_text(url)
        rows = parse_eastmoney_search(
            payload,
            company=f"行业:{industry}",
            display_name=industry,
            ticker=f"industry:{industry}",
            market="行业",
            cutoff=cutoff,
            lookback_days=window_days,
            scope="industry",
        )
        if auxiliary_news_limit > news_limit:
            auxiliary_payload = http_text(
                build_eastmoney_search_url(f"{query_name} 行业", auxiliary_news_limit)
            )
            auxiliary_rows = parse_eastmoney_search(
                auxiliary_payload,
                company=f"行业:{industry}",
                display_name=industry,
                ticker=f"industry:{industry}",
                market="行业",
                cutoff=cutoff,
                lookback_days=window_days,
                scope="industry",
            )
            rows.extend(row for row in auxiliary_rows if not row.get("score_eligible", True))
        for row in rows:
            row["retrieval_window_days"] = window_days
            row["retrieval_window_type"] = window_type
        return rows

    rows = fetch_window(lookback_days, "recent")
    if rows or fallback_lookback_days <= lookback_days:
        return cap_auxiliary_news(merge_news_sources(rows), auxiliary_news_limit, context_analysis_limit)
    return cap_auxiliary_news(
        merge_news_sources(fetch_window(fallback_lookback_days, "fallback")),
        auxiliary_news_limit,
        context_analysis_limit,
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


def score_with_llm(
    batch: list[dict[str, Any]], config: LLMConfig, provider_label: str = "primary"
) -> dict[str, dict[str, Any]]:
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
    if config.reasoning_effort:
        request_payload["reasoning_effort"] = config.reasoning_effort
    if config.json_mode:
        request_payload["response_format"] = {"type": "json_object"}
    if config.max_tokens:
        request_payload["max_tokens"] = config.max_tokens
    body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    response = http_json(
        config.endpoint,
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        body=body,
        timeout=config.timeout_seconds,
        attempts=config.max_retries + 1,
        retry_backoff_seconds=config.retry_backoff_seconds,
    )
    choices = response.get("choices") or []
    if not choices:
        raise SentimentError("LLM response has no choices")
    message = choices[0].get("message", {})
    content = message.get("content") or message.get("reasoning_content", "")
    content_text = content if isinstance(content, str) else str(content or "")
    try:
        parsed = parse_json_block(content_text)
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        finish_reason = choices[0].get("finish_reason")
        content_bytes = len(content_text.encode("utf-8"))
        raise SentimentError(
            "LLM content malformed JSON "
            f"(provider={provider_label}, finish_reason={finish_reason!r}, "
            f"content_bytes={content_bytes})"
        ) from exc
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
            "scoring_method": f"llm:{provider_label}:{config.model}",
        }
    return scores


def score_articles(
    articles: list[dict[str, Any]],
    primary_config: LLMConfig | None,
    review_config: LLMConfig | None,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Score formal news and a bounded contextual subset of auxiliary news.

    A/B articles remain eligible for the formal score.  C/D articles can now
    be interpreted by the models, but are retained as contextual evidence and
    never silently promoted to formal source quality.
    """
    if primary_config is None:
        raise SentimentError("primary model configuration is required")
    if not articles:
        return [], [], []
    scoreable_articles = [
        article for article in articles if article.get("score_eligible", True)
    ]
    contextual_articles = [
        article
        for article in articles
        if not article.get("score_eligible", True)
        and article.get("context_analysis_eligible", True)
    ]
    untouched_auxiliary_articles = [
        mark_auxiliary_article(article)
        for article in articles
        if not article.get("score_eligible", True)
        and not article.get("context_analysis_eligible", True)
    ]
    model_articles = scoreable_articles + contextual_articles
    if not model_articles:
        return untouched_auxiliary_articles, [], []
    requires_review = any(
        article.get("market") == "A股" or article.get("scope") == "industry"
        for article in model_articles
    )
    if requires_review and review_config is None:
        raise SentimentError("A-share dual-model scoring requires the review model configuration")

    def collect_scores(
        target_articles: list[dict[str, Any]], config: LLMConfig, provider_label: str
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        batches = list(chunks(target_articles, config.batch_size))
        scores: dict[str, dict[str, Any]] = {}
        failures: list[dict[str, Any]] = []

        def failure_record(
            item: dict[str, Any], reason: str
        ) -> dict[str, Any]:
            return {
                "id": item.get("id"),
                "ticker": item.get("ticker"),
                "company": clean_text(
                    item.get("display_name") or item.get("company") or item.get("ticker"),
                    120,
                ),
                "market": item.get("market"),
                "title": clean_text(item.get("title"), 160),
                "provider": provider_label,
                "retry_count": config.missing_result_retries,
                "reason": clean_text(reason, 500),
            }

        def recover_items(
            items: list[dict[str, Any]], reason: str
        ) -> None:
            """Retry unresolved items one at a time to avoid gateway omissions."""
            remaining = list(items)
            last_errors: dict[str, str] = {}
            for retry_round in range(config.missing_result_retries):
                if not remaining:
                    break
                if retry_round:
                    time.sleep(
                        min(
                            60.0,
                            config.retry_backoff_seconds * (2 ** (retry_round - 1)),
                        )
                    )
                next_remaining: list[dict[str, Any]] = []
                with ThreadPoolExecutor(
                    max_workers=min(config.workers, len(remaining))
                ) as retry_executor:
                    retry_futures = {
                        retry_executor.submit(
                            score_with_llm, [item], config, provider_label
                        ): item
                        for item in remaining
                    }
                    for retry_future in as_completed(retry_futures):
                        item = retry_futures[retry_future]
                        try:
                            retry_scores = retry_future.result()
                        except Exception as exc:  # noqa: BLE001 - record and skip after recovery attempts
                            last_errors[item["id"]] = clean_text(exc, 240)
                            next_remaining.append(item)
                            continue
                        item_score = retry_scores.get(item["id"])
                        if item_score is None:
                            last_errors[item["id"]] = "单条重试未返回该新闻的有效评分"
                            next_remaining.append(item)
                        else:
                            scores[item["id"]] = item_score
                remaining = next_remaining
            if remaining:
                for item in remaining:
                    detail = (
                        f"{reason}; {config.missing_result_retries} 次单条重试后仍未得到有效评分"
                    )
                    if last_errors.get(item["id"]):
                        detail += f"；最后错误：{last_errors[item['id']]}"
                    failures.append(failure_record(item, detail))

        with ThreadPoolExecutor(max_workers=min(config.workers, len(batches))) as executor:
            futures = {
                executor.submit(score_with_llm, batch, config, provider_label): batch
                for batch in batches
            }
            for future in as_completed(futures):
                batch = futures[future]
                try:
                    batch_scores = future.result()
                except Exception as exc:  # noqa: BLE001 - fail closed for every provider error
                    recover_items(batch, f"batch {batch[0]['id']} failed: {exc}")
                    continue
                scores.update(batch_scores)
                missing = {item["id"] for item in batch} - set(batch_scores)
                if missing:
                    missing_items = [item for item in batch if item["id"] in missing]
                    recover_items(
                        missing_items,
                        f"batch {batch[0]['id']} returned incomplete results",
                    )
        expected = {article["id"] for article in target_articles}
        missing = expected - set(scores)
        recorded = {failure.get("id") for failure in failures}
        for item in target_articles:
            if item["id"] in missing and item["id"] not in recorded:
                failures.append(
                    failure_record(
                        item,
                        f"{provider_label} 模型未返回有效评分；已完成 {config.missing_result_retries} 次单条重试",
                    )
                )
        return scores, failures

    primary_scores, primary_failures = collect_scores(
        model_articles, primary_config, "primary"
    )
    primary_success_articles = [
        article for article in model_articles if article["id"] in primary_scores
    ]
    review_articles = [
        article
        for article in primary_success_articles
        if article.get("market") == "A股" or article.get("scope") == "industry"
    ]
    review_scores = (
        collect_scores(review_articles, review_config, "review")
        if review_articles
        else ({}, [])
    )
    review_score_map, review_failures = review_scores
    skipped_articles = primary_failures + review_failures
    skipped_ids = {failure.get("id") for failure in skipped_articles}
    scoring_warnings = [
        (
            f"情绪评分跳过：{failure.get('market') or '未知市场'} "
            f"{failure.get('ticker') or failure.get('id')} "
            f"{failure.get('company') or ''}（{failure.get('provider')}，"
            f"重试{failure.get('retry_count', 0)}次）：{failure.get('reason')}"
        ).strip()
        for failure in skipped_articles
    ]
    scored: list[dict[str, Any]] = []
    for article in primary_success_articles:
        if article["id"] in skipped_ids:
            continue
        primary = dict(primary_scores[article["id"]])
        needs_review = article.get("market") == "A股" or article.get("scope") == "industry"
        if not needs_review:
            combined = {**article, **primary, "scoring_method": f"llm:single:{primary_config.model}"}
            apply_company_relevance_guard(combined, combined)
            scored.append(combined)
            continue
        review = dict(review_score_map[article["id"]])
        apply_company_relevance_guard(article, primary)
        apply_company_relevance_guard(article, review)
        direction_gap = abs(float(primary["direction"]) - float(review["direction"]))
        direction_sign_agrees = (
            float(primary["direction"]) == 0
            or float(review["direction"]) == 0
            or (float(primary["direction"]) > 0) == (float(review["direction"]) > 0)
        )
        event_type = primary["event_type"] if primary["event_type"] == review["event_type"] else "模型分歧"
        combined = {
            **article,
            "direction": round((float(primary["direction"]) + float(review["direction"])) / 2, 4),
            "impact": int(round((int(primary["impact"]) + int(review["impact"])) / 2)),
            "relevance": round(min(float(primary["relevance"]), float(review["relevance"])), 4),
            "confidence": round(min(float(primary["confidence"]), float(review["confidence"])), 4),
            "event_type": event_type,
            "scoring_method": f"llm:dual:{primary_config.model}+{review_config.model}",
            "model_review": {
                "primary_direction": primary["direction"],
                "review_direction": review["direction"],
                "direction_gap": round(direction_gap, 4),
                "direction_sign_agrees": direction_sign_agrees,
                "primary_event_type": primary["event_type"],
                "review_event_type": review["event_type"],
            },
        }
        if not article.get("score_eligible", True):
            combined["score_eligible"] = False
            combined["context_score_eligible"] = True
            combined["score_exclusion_reason"] = (
                f"来源等级{article.get('source_tier', 'C')}：模型已分析，但仅进入辅助情绪"
            )
        apply_company_relevance_guard(combined, combined)
        scored.append(combined)
    scored.extend(untouched_auxiliary_articles)
    return scored, scoring_warnings, skipped_articles


def time_decay(article: dict[str, Any], cutoff: datetime) -> float:
    published = parse_datetime(article.get("published_at"))
    if published is None:
        age_days = 1.0
    else:
        age_days = max(0.0, (cutoff - published).total_seconds() / 86400)
    event_type = article.get("event_type") or "一般新闻"
    half_life = EVENT_HALF_LIFE_DAYS.get(event_type)
    if half_life is None:
        # Remote models may return a more specific label such as "股份回购";
        # map it back to the canonical event family before using the default.
        half_life = EVENT_HALF_LIFE_DAYS.get(
            detect_event_type(f"{article.get('title', '')} {article.get('summary', '')}"),
            2.0,
        )
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


def contextual_source_weight(article: dict[str, Any]) -> float:
    """Discount contextual evidence without treating it as formal A/B evidence."""
    if article.get("score_eligible", True):
        return 1.0 if article.get("source_tier") == "A" else 0.8
    if article.get("context_score_eligible", False):
        return {"C": 0.35, "D": 0.15}.get(article.get("source_tier"), 0.2)
    return 0.0


def aggregate_news(
    articles: list[dict[str, Any]],
    cutoff: datetime,
    *,
    primary_lookback_days: int = DEFAULT_PRIMARY_LOOKBACK_DAYS,
    include_context: bool = False,
) -> dict[str, Any]:
    """Aggregate formal news, optionally including AI-analyzed context news."""
    scoreable_articles = [
        article for article in articles if article.get("score_eligible", True)
    ]
    auxiliary_articles = [
        article for article in articles if not article.get("score_eligible", True)
    ]
    context_articles = [
        article
        for article in articles
        if article.get("score_eligible", True)
        or (include_context and article.get("context_score_eligible", False))
    ]
    relevant_articles = [
        article for article in context_articles
        if float(article.get("relevance", 0)) >= 0.5
    ]
    numerator = 0.0
    denominator = 0.0
    freshness_numerator = 0.0
    freshness_denominator = 0.0
    classified_count = 0
    high_impact_negative = 0
    methods: set[str] = set()
    rendered_items: list[dict[str, Any]] = []
    fallback_articles = [
        article
        for article in context_articles
        if article.get("retrieval_window_type") == "fallback"
    ]
    relevant_identity = {id(article) for article in relevant_articles}

    def render_news_item(article: dict[str, Any], included: bool) -> dict[str, Any]:
        is_scoreable = bool(article.get("score_eligible", True))
        is_contextual = bool(
            include_context
            and not is_scoreable
            and article.get("context_score_eligible", False)
        )
        decay = time_decay(article, cutoff) if is_scoreable or is_contextual else None
        return {
            "title": article["title"],
            "summary": article.get("summary", ""),
            "publisher": article["publisher"],
            "url": article["url"],
            "published_at": article["published_at"],
            "event_type": article["event_type"],
            "direction": article.get("direction") if is_scoreable or is_contextual else None,
            "impact": article.get("impact") if is_scoreable or is_contextual else None,
            "relevance": article.get("relevance") if is_scoreable or is_contextual else None,
            "confidence": article.get("confidence") if is_scoreable or is_contextual else None,
            "time_weight": round(decay, 4) if decay is not None else None,
            "contextual": is_contextual,
            "source_weight": round(contextual_source_weight(article), 4)
            if is_scoreable or is_contextual
            else None,
            "retrieval_window_days": article.get("retrieval_window_days", primary_lookback_days),
            "scoring_method": article["scoring_method"],
            "included": included,
            "source_tier": article.get("source_tier", "未知"),
            "source_tier_label": article.get("source_tier_label", "来源等级待复核"),
            "score_eligible": is_scoreable,
            "verification_status": article.get("verification_status", "待复核"),
            "source_via": article.get("source_via", "未知渠道"),
            "filter_reason": (
                None
                if included
                else article.get("score_exclusion_reason")
                if not is_scoreable
                else "相关性低于评分阈值 0.5"
            ),
        }

    sorted_articles = sorted(articles, key=lambda item: item.get("published_at") or "", reverse=True)
    captured_items = [
        render_news_item(article, id(article) in relevant_identity) for article in sorted_articles
    ]
    for article in sorted(relevant_articles, key=lambda item: item.get("published_at") or "", reverse=True):
        decay = time_decay(article, cutoff)
        weight = (
            float(article["impact"])
            * float(article["relevance"])
            * float(article["confidence"])
            * decay
        )
        if include_context:
            weight *= contextual_source_weight(article)
        base_weight = (
            float(article["impact"])
            * float(article["relevance"])
            * float(article["confidence"])
        )
        if include_context:
            base_weight *= contextual_source_weight(article)
        direction = float(article["direction"])
        numerator += direction * weight
        denominator += weight
        freshness_numerator += base_weight * decay
        freshness_denominator += base_weight
        if abs(direction) >= 0.15:
            classified_count += 1
        if direction <= -0.35 and int(article["impact"]) >= 3:
            high_impact_negative += 1
        methods.add(str(article["scoring_method"]))
        rendered_items.append(render_news_item(article, True))
    if not relevant_articles or denominator <= 0:
        if not articles:
            recency_state = "无可用新闻"
        elif auxiliary_articles and not scoreable_articles:
            recency_state = "抓到相关新闻，但来源仅供辅助，未计入评分"
        elif fallback_articles:
            recency_state = f"近{primary_lookback_days}日无新消息，近{max(int(article.get('retrieval_window_days', primary_lookback_days)) for article in fallback_articles)}日无有效相关新闻"
        else:
            recency_state = "抓到新闻但没有可评分的有效相关新闻"
        return {
            "status": "unavailable",
            "score_0_100": None,
            "state": recency_state,
            "news_recency": "none" if not articles else "no_relevant_news",
            "recency_state": recency_state,
            "confidence": "无数据",
            "article_count": len(articles),
            "score_article_count": len(scoreable_articles),
            "auxiliary_article_count": len(auxiliary_articles),
            "context_article_count": len(context_articles) if include_context else len(scoreable_articles),
            "context_only_article_count": sum(
                1 for article in context_articles if not article.get("score_eligible", True)
            )
            if include_context
            else 0,
            "score_scope": "formal_and_context" if include_context else "formal",
            "relevant_article_count": len(relevant_articles),
            "classified_count": 0,
            "high_impact_negative_count": 0,
            "scoring_methods": [],
            "items": rendered_items,
            "captured_items": captured_items,
        }
    normalized = clamp(numerator / denominator, -1, 1)
    freshness_factor = None
    if fallback_articles and freshness_denominator > 0:
        # A fallback headline should inform the direction, but cannot produce
        # the same conviction as a fresh headline. Keep a small floor so one
        # old article does not become artificially neutral.
        freshness_factor = round(
            clamp(freshness_numerator / freshness_denominator, 0.25, 1.0), 4
        )
        normalized = clamp(normalized * freshness_factor, -1, 1)
    score = round(50 + normalized * 50, 2)
    if len(relevant_articles) >= 4 and classified_count >= 2 and any(method.startswith("llm:") for method in methods):
        confidence = "较高"
    elif len(relevant_articles) >= 3 and classified_count >= 1:
        confidence = "中等"
    else:
        confidence = "较低"
    recency_state = (
        f"近{primary_lookback_days}日无新消息，参考近{max(int(article.get('retrieval_window_days', primary_lookback_days)) for article in fallback_articles)}日"
        if fallback_articles
        else f"近{primary_lookback_days}日有新消息"
    )
    return {
        "status": "ok",
        "score_0_100": score,
        "state": sentiment_state(score),
        "news_recency": "fallback" if fallback_articles else "recent",
        "recency_state": recency_state,
        "freshness_factor": freshness_factor,
        "confidence": confidence,
        "article_count": len(articles),
        "score_article_count": len(scoreable_articles),
        "auxiliary_article_count": len(auxiliary_articles),
        "context_article_count": len(context_articles) if include_context else len(scoreable_articles),
        "context_only_article_count": sum(
            1 for article in context_articles if not article.get("score_eligible", True)
        )
        if include_context
        else 0,
        "score_scope": "formal_and_context" if include_context else "formal",
        "relevant_article_count": len(relevant_articles),
        "classified_count": classified_count,
        "high_impact_negative_count": high_impact_negative,
        "scoring_methods": sorted(methods),
        "items": rendered_items,
        "captured_items": captured_items,
    }


def merge_sentiment_views(
    formal: dict[str, Any], contextual: dict[str, Any]
) -> dict[str, Any]:
    """Expose formal and contextual views without hiding source quality."""
    result = dict(formal)
    result["formal_score_0_100"] = formal.get("score_0_100")
    result["formal_status"] = formal.get("status")
    result["context_score_0_100"] = contextual.get("score_0_100")
    result["context_state"] = contextual.get("state")
    result["context_confidence"] = contextual.get("confidence")
    result["context_article_count"] = contextual.get("context_article_count", 0)
    result["context_only_article_count"] = contextual.get("context_only_article_count", 0)
    result["context_scoring_methods"] = contextual.get("scoring_methods", [])
    if contextual.get("score_0_100") is not None:
        result["score_0_100"] = contextual["score_0_100"]
        result["state"] = contextual.get("state")
        result["confidence"] = contextual.get("confidence")
        result["score_scope"] = "正式+辅助AI分析"
        if formal.get("score_0_100") is None:
            result["status"] = "context_only"
            result["score_scope"] = "仅辅助AI分析"
    else:
        result["score_scope"] = "正式来源"
    return result


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
    """Combine three sentiment layers without renormalizing missing data."""
    news_score = news.get("score_0_100")
    industry_score = (industry or {}).get("score_0_100")
    market_score = market_sentiment.get("score_0_100") if market else None
    if market != "A股":
        market_score = None
    if news_score is None and industry_score is None and market_score is None:
        return {
            "status": "unavailable",
            "score_0_100": None,
            "state": news.get("recency_state") or news.get("state") or "无数据",
            "coverage": {"company": False, "industry": False, "market": False},
        }
    # Until a company-to-industry exposure map exists, use a conservative
    # 0.6 transmission coefficient for a mapped constituent. This keeps an
    # industry shock meaningful without treating every constituent equally.
    industry_exposure = 0.6 if industry_score is not None else 0.0
    layer_scores = {
        "company": round(float(news_score), 2) if news_score is not None else None,
        "industry": round(float(industry_score), 2) if industry_score is not None else None,
        "industry_adjusted": round(
            50 + (float(industry_score) - 50) * industry_exposure, 2
        )
        if industry_score is not None
        else None,
        "market": round(float(market_score), 2) if market_score is not None else None,
    }
    weights = {"company": 0.60, "industry": 0.25, "market": 0.15}
    score = 50.0
    if news_score is not None:
        score += weights["company"] * (float(news_score) - 50)
    if industry_score is not None:
        score += weights["industry"] * (
            layer_scores["industry_adjusted"] - 50
        )
    if market_score is not None:
        score += weights["market"] * (float(market_score) - 50)
    score = round(clamp(score, 0, 100), 2)
    company_formal_available = news.get("formal_score_0_100", news_score) is not None
    status = "ok" if company_formal_available else "context_only"
    method = "个股60% + 行业25%（行业传导系数0.6）+ 市场15%；缺失层不放大其他层权重"
    return {
        "status": status,
        "score_0_100": score,
        "state": sentiment_state(score),
        "method": method,
        "weights": weights,
        "layer_scores": layer_scores,
        "coverage": {
            "company": news_score is not None,
            "industry": industry_score is not None,
            "market": market_score is not None,
        },
        "industry_exposure": industry_exposure,
        "confidence": "较低" if status == "context_only" else news.get("confidence", "较低"),
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
    fallback_lookback_days: int = DEFAULT_FALLBACK_LOOKBACK_DAYS,
    news_limit: int,
    auxiliary_news_limit: int = 60,
    context_analysis_limit: int = DEFAULT_CONTEXT_ANALYSIS_LIMIT,
    rss_news_limit: int = 20,
    workers: int,
    markets: set[str] | None = None,
    company_limit: int | None = None,
    llm_config: LLMConfig | None = None,
    review_llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    selected_markets = markets or SUPPORTED_MARKETS
    universe = load_universe(board_path, selected_markets)
    if company_limit is not None:
        universe = universe[:company_limit]
    if not universe:
        raise SentimentError(
            f"no companies found for markets: {', '.join(sorted(selected_markets))}"
        )

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
                fetch_company_news_result,
                item,
                display_name=display_names[item["ticker"]],
                cutoff=cutoff,
                lookback_days=lookback_days,
                news_limit=news_limit,
                auxiliary_news_limit=auxiliary_news_limit,
                context_analysis_limit=context_analysis_limit,
                rss_news_limit=rss_news_limit,
                fallback_lookback_days=fallback_lookback_days,
            ): item
            for item in universe
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                rows, source_warnings = future.result()
                articles_by_ticker[item["ticker"]] = rows
                warnings.extend(
                    f"{item['ticker']} source warning: {warning}" for warning in source_warnings
                )
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
                auxiliary_news_limit=auxiliary_news_limit,
                context_analysis_limit=context_analysis_limit,
                fallback_lookback_days=fallback_lookback_days,
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
    scored_articles, scoring_warnings, skipped_articles = score_articles(
        all_articles, llm_config, review_llm_config
    )
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
        formal_sentiment = aggregate_news(
            scored_by_industry[industry], cutoff, primary_lookback_days=lookback_days
        )
        contextual_sentiment = aggregate_news(
            scored_by_industry[industry],
            cutoff,
            primary_lookback_days=lookback_days,
            include_context=True,
        )
        industry_details[industry] = {
            "industry": industry,
            "company_count": sum(1 for value in industries_by_ticker.values() if value == industry),
            "sentiment": merge_sentiment_views(formal_sentiment, contextual_sentiment),
        }

    companies = []
    for item in universe:
        formal_news = aggregate_news(
            scored_by_ticker[item["ticker"]], cutoff, primary_lookback_days=lookback_days
        )
        contextual_news = aggregate_news(
            scored_by_ticker[item["ticker"]],
            cutoff,
            primary_lookback_days=lookback_days,
            include_context=True,
        )
        news = merge_sentiment_views(formal_news, contextual_news)
        crowding = crowding_snapshot(item["ticker"], item["market"], hot_by_code)
        industry = industries_by_ticker[item["ticker"]]
        industry_sentiment = industry_details.get(industry, {}).get("sentiment")
        industry_summary = None
        if industry_sentiment:
            industry_summary = {
                key: value
                for key, value in industry_sentiment.items()
                if key not in {"items", "captured_items"}
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

    successful_news = sum(
        1 for company in companies if company["news_sentiment"].get("score_0_100") is not None
    )
    formal_news_available = sum(
        1
        for company in companies
        if company["news_sentiment"].get("formal_score_0_100") is not None
    )
    successful_industry_news = sum(
        1
        for detail in industry_details.values()
        if detail["sentiment"].get("score_0_100") is not None
    )
    formal_industry_news = sum(
        1
        for detail in industry_details.values()
        if detail["sentiment"].get("formal_score_0_100") is not None
    )
    return {
        "schema_version": 1,
        "generated_at": now.astimezone(SHANGHAI_TIMEZONE).isoformat(),
        "data_cutoff": as_of.isoformat(),
        "scope": sorted({item["market"] for item in universe}),
        "status": "ok" if not warnings and not skipped_articles else "partial",
        "dashboard_integration": True,
        "universe_source": str(board_path.relative_to(ROOT)) if board_path.is_relative_to(ROOT) else str(board_path),
        "company_count": len(companies),
        "company_news_available_count": successful_news,
        "company_formal_news_available_count": formal_news_available,
        "industry_count": len(industry_names),
        "industry_news_available_count": successful_industry_news,
        "industry_formal_news_available_count": formal_industry_news,
        "scoring_mode": (
            f"remote-mixed-llm:{llm_config.model}+A股/行业复核:{review_llm_config.model}"
            if llm_config and review_llm_config
            else f"remote-primary-llm:{llm_config.model}"
            if llm_config
            else "invalid-primary-model-configuration"
        ),
        "news_policy": {
            "primary_lookback_days": lookback_days,
            "fallback_lookback_days": fallback_lookback_days,
            "fallback_only_when_primary_window_is_empty": True,
            "score_news_limit": news_limit,
            "auxiliary_news_limit": auxiliary_news_limit,
            "context_analysis_limit": context_analysis_limit,
            "auxiliary_news_sources": "C/D enter bounded contextual AI analysis; they do not become formal A/B evidence",
            "rss_news_limit_per_channel": rss_news_limit,
            "rss_channels": ["Google News RSS", "Bing News RSS", "Google News indexed Xueqiu pages"],
            "direct_auxiliary_channels": [
                "Sina Finance individual-stock news",
                "Baidu News via read-only text proxy",
            ],
        },
        "source_policy": {
            "A": "一手披露：直连巨潮资讯公告、交易所、监管机构、公司公告或公司投资者关系页面；可评分",
            "B": "专业媒体：需视为二手来源，当前可进入评分但明确标注单一来源；重要事件建议人工核对一手公告",
            "C": "聚合/其他媒体：可进入有限度上下文AI分析，但不进入正式来源分",
            "D": "社区/传闻：可进入有限度上下文AI分析，但不进入正式来源分，也不能单独形成方向判断",
            "company_score_rule": "个股60% + 行业25%（默认传导系数0.6）+ A股市场15%；缺失层不放大其他层权重",
        },
        "market_sentiment": {"A股": market_sentiment, "港股": {"status": "not_available_in_v1"}},
        "industry_sentiments": industry_details,
        "companies": companies,
        "warnings": warnings,
        "skipped_count": len(skipped_articles),
        "skipped_articles": skipped_articles,
        "method_notes": [
            "新闻分包含方向、影响强度、相关性、置信度和事件半衰期。",
            "A股和行业新闻由主模型与复核模型共同评分；C/D辅助新闻按上限进入AI分析，但仍保留来源降权，不会升级为正式A/B证据。官方公告优先直连巨潮资讯；任一模型失败、超时或返回缺失时，先进行单条重试，仍失败的新闻跳过并记录，其余成功结果继续写入。",
            f"新闻抓取优先近{lookback_days}日；若窗口内没有抓到新闻，则回溯近{fallback_lookback_days}日，并标注为参考旧闻。",
            "个股情绪保留正式来源分，同时展示含辅助AI分析的上下文分；A/B进入正式分，C/D只按降权上下文进入。",
            "行业权威来源可标为行业A级，但行业范围和对个股的传导系数仍单独记录。",
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
    parser.add_argument("--site-output", type=Path, default=DEFAULT_SITE_OUTPUT)
    parser.add_argument("--status-output", type=Path, default=DEFAULT_STATUS_OUTPUT)
    parser.add_argument("--as-of", type=date.fromisoformat, help="end-of-day cutoff (YYYY-MM-DD)")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_PRIMARY_LOOKBACK_DAYS)
    parser.add_argument(
        "--fallback-lookback-days",
        type=int,
        default=DEFAULT_FALLBACK_LOOKBACK_DAYS,
        help="fallback news window when the primary window has no results",
    )
    parser.add_argument("--news-limit", type=int, default=8)
    parser.add_argument(
        "--auxiliary-news-limit",
        type=int,
        default=60,
        help="C/D auxiliary-news pool size",
    )
    parser.add_argument(
        "--context-analysis-limit",
        type=int,
        default=DEFAULT_CONTEXT_ANALYSIS_LIMIT,
        help="per company/industry maximum auxiliary headlines sent to models",
    )
    parser.add_argument(
        "--rss-news-limit",
        type=int,
        default=20,
        help="per-channel RSS result limit for C-level auxiliary context",
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--markets",
        nargs="+",
        choices=sorted(SUPPORTED_MARKETS),
        default=sorted(SUPPORTED_MARKETS),
        help="markets to include in the sentiment snapshot",
    )
    parser.add_argument("--company-limit", type=int, help="bounded smoke-test universe")
    parser.add_argument("--no-archive", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    now = datetime.now(tz=SHANGHAI_TIMEZONE)
    as_of = effective_as_of(now, args.as_of)
    try:
        if (
            args.lookback_days < 1
            or args.fallback_lookback_days < 1
            or args.news_limit < 1
            or args.auxiliary_news_limit < 1
            or args.context_analysis_limit < 0
            or args.rss_news_limit < 1
            or args.workers < 1
        ):
            raise SentimentError(
                "lookback-days, fallback-lookback-days, news limits and workers must be positive; context-analysis-limit cannot be negative"
            )
        if args.fallback_lookback_days < args.lookback_days:
            raise SentimentError("fallback-lookback-days must be >= lookback-days")
        if args.auxiliary_news_limit < args.news_limit:
            raise SentimentError("auxiliary-news-limit must be >= news-limit")
        primary_config = LLMConfig.from_environment("SENTIMENT_LLM_")
        review_config = LLMConfig.from_environment("SENTIMENT_REVIEW_")
        if primary_config is None:
            raise SentimentError(
                "主模型配置不完整：请填写 SENTIMENT_LLM_* 的 API_KEY、MODEL、ENDPOINT"
            )
        snapshot = build_snapshot(
            board_path=args.board.resolve(),
            registry_path=args.registry.resolve(),
            as_of=as_of,
            now=now,
            lookback_days=args.lookback_days,
            fallback_lookback_days=args.fallback_lookback_days,
            news_limit=args.news_limit,
            auxiliary_news_limit=args.auxiliary_news_limit,
            context_analysis_limit=args.context_analysis_limit,
            rss_news_limit=args.rss_news_limit,
            workers=args.workers,
            markets=set(args.markets),
            company_limit=args.company_limit,
            llm_config=primary_config,
            review_llm_config=review_config,
        )
        write_json(args.output.resolve(), snapshot)
        write_json(args.site_output.resolve(), snapshot)
        status = {
            "status": snapshot["status"],
            "generated_at": snapshot["generated_at"],
            "data_cutoff": snapshot["data_cutoff"],
            "scoring_mode": snapshot["scoring_mode"],
            "company_count": snapshot["company_count"],
            "skipped_count": snapshot.get("skipped_count", 0),
            "skipped_articles": snapshot.get("skipped_articles", []),
            "warnings": snapshot.get("warnings", []),
            "message": (
                "情绪部分更新；失败项目已重试后跳过，其余成功结果已写入。"
                if snapshot.get("skipped_count", 0)
                else "情绪数据更新完成。"
            ),
        }
        write_json(args.status_output.resolve(), status)
        if not args.no_archive:
            archive_path = args.archive_dir.resolve() / f"{as_of.isoformat()}.json"
            if not archive_path.exists():
                write_json(archive_path, snapshot)
        print(json.dumps({**status, "output": str(args.output.resolve())}, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - status must be published for every failed run
        status = {
            "status": "error",
            "generated_at": now.isoformat(),
            "data_cutoff": as_of.isoformat(),
            "error": str(exc),
            "message": "情绪更新失败；看板继续显示上一份成功快照。",
        }
        try:
            write_json(args.status_output.resolve(), status)
        except OSError:
            pass
        print(json.dumps(status, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
