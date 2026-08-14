#!/usr/bin/env python3
"""Generate auditable technical-analysis snapshots and Markdown reports.

TA-Lib is the only indicator engine. The surrounding code handles data quality,
provider cross-checks, conservative state classification, and report rendering.
It never places orders and does not replace fundamental or valuation research.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
MINIMUM_OBSERVATIONS = 200
PREFERRED_OBSERVATIONS = 260
INTRADAY_INTERVAL = "30m"
INTRADAY_MINIMUM_OBSERVATIONS = 100
INTRADAY_PREFERRED_OBSERVATIONS = 200
INTRADAY_LOOKBACK_DAYS = 59
MAX_STALENESS_DAYS = 7
CROSS_SOURCE_TOLERANCE_PCT = 1.0
PRICE_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
EXPLICIT_PRICE_BAND_PATTERN = re.compile(
    r"(?:≤|<=|<|低于|以下|不高于|小于)?\s*"
    r"\d+(?:\.\d+)?\s*"
    r"(?:[-—–]\s*\d+(?:\.\d+)?\s*)?"
    r"(?:元|人民币|RMB|CNY|港元|HKD|美元|USD)",
    re.IGNORECASE,
)
REPORT_DATE_PATTERN = re.compile(
    r"(?<!\d)(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})(?:日)?"
)
PRIMARY_REPORT_PATTERN = re.compile(
    r"(?:research|investment-team|研究报告|投资研究报告)",
    re.IGNORECASE,
)
AUXILIARY_REPORT_PATTERN = re.compile(
    r"(?:technical-analysis|thesis|checklist|management|earnings|news|MOC)",
    re.IGNORECASE,
)
PROJECT_PATH_PATTERN = re.compile(r"`((?:reports|research|data)/[^`\r\n]+)`")


class TechnicalAnalysisError(RuntimeError):
    """Raised when an analysis cannot be produced without misleading output."""


@dataclass(frozen=True)
class PriceRow:
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    bar_time: datetime | None = None


def finite_number(value: Any) -> float | None:
    """Convert one value to a finite float, otherwise return None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalize_ticker(ticker: str, market: str | None = None) -> tuple[str, str, str]:
    """Return project ticker, Yahoo symbol, and normalized display market."""
    raw = ticker.strip().upper().replace(" ", "")
    market_hint = (market or "").strip()
    if not raw:
        raise TechnicalAnalysisError("ticker is required")

    if raw.endswith(".SH"):
        return raw, f"{raw[:-3]}.SS", "A股"
    if raw.endswith(".SZ"):
        return raw, raw, "A股"
    if raw.endswith(".BJ"):
        return raw, raw, "A股"
    if raw.endswith(".HK"):
        code = raw[:-3]
        if not code.isdigit():
            raise TechnicalAnalysisError(f"invalid Hong Kong ticker: {ticker}")
        numeric_code = str(int(code))
        project_ticker = f"{numeric_code.zfill(5)}.HK"
        return project_ticker, f"{numeric_code.zfill(4)}.HK", "港股"
    if raw.isdigit() and len(raw) == 6:
        suffix = "SH" if raw.startswith(("6", "9", "5")) else "SZ"
        return normalize_ticker(f"{raw}.{suffix}", market_hint)
    if raw.isdigit() and market_hint == "港股":
        return normalize_ticker(f"{raw}.HK", market_hint)
    if re.fullmatch(r"[A-Z][A-Z0-9.^=-]{0,14}", raw):
        return raw, raw, "美股" if market_hint in {"", "美股"} else market_hint
    raise TechnicalAnalysisError(f"unsupported ticker format: {ticker}")


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise TechnicalAnalysisError(f"invalid date {value!r}; expected YYYY-MM-DD") from error


def dates_after_labels(lines: list[str], labels: tuple[str, ...]) -> list[date]:
    """Extract dates that occur after explicit labels, never from filenames."""
    matches: list[date] = []
    for line in lines[:120]:
        folded = line.casefold()
        for label in labels:
            start = folded.find(label.casefold())
            if start < 0:
                continue
            match = REPORT_DATE_PATTERN.search(line[start + len(label) :])
            if not match:
                continue
            try:
                matches.append(date(*(int(part) for part in match.groups())))
            except ValueError:
                continue
    return matches


def report_context_dates(path: Path) -> tuple[date | None, date | None]:
    """Return an explicit market-data cutoff and report date from one report."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cutoff_dates = dates_after_labels(
        lines,
        ("数据截止", "数据截至", "截止日期", "data cutoff", "as of", "股价截至", "行情基准"),
    )
    report_dates = dates_after_labels(
        lines,
        ("报告日期", "研究日期", "撰写日期", "报告完成日", "研究完成日"),
    )
    return (
        max(cutoff_dates) if cutoff_dates else None,
        max(report_dates) if report_dates else None,
    )


def latest_primary_report(directory: Path) -> Path | None:
    """Select the latest full company report by explicit in-report dates."""
    reports = [
        path
        for path in directory.glob("*.md")
        if path.is_file()
        and path.name.casefold() not in {"readme.md", "moc.md"}
        and not AUXILIARY_REPORT_PATTERN.search(path.name)
    ]
    primary = [path for path in reports if PRIMARY_REPORT_PATTERN.search(path.name)]
    candidates = primary or reports
    if not candidates:
        return None

    def rank(path: Path) -> tuple[date, date, str]:
        cutoff, report_date = report_context_dates(path)
        return (
            cutoff or date.min,
            report_date or date.min,
            path.name.casefold(),
        )

    return max(candidates, key=rank)


def referenced_project_files(report_path: Path, repo_root: Path = ROOT) -> list[str]:
    """Return existing project-local files explicitly cited by a report."""
    text = report_path.read_text(encoding="utf-8", errors="replace")
    paths: set[str] = set()
    for raw_path in PROJECT_PATH_PATTERN.findall(text):
        relative = Path(raw_path.strip())
        if relative.is_absolute() or ".." in relative.parts:
            continue
        resolved = repo_root / relative
        if resolved.is_file():
            paths.add(relative.as_posix())
    return sorted(paths)


def resolve_project_context(
    company: str,
    ticker: str | None = None,
    repo_root: Path = ROOT,
) -> dict[str, Any]:
    """Resolve a company name to its ticker, latest report, and cited files."""
    try:
        import report_routing

        registry = report_routing.load_registry(
            repo_root / "data" / "report-routing" / "company_registry.json"
        )
        entry = report_routing.find_company(registry, company, ticker)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise TechnicalAnalysisError(f"cannot load project company registry: {error}") from error
    if not entry:
        raise TechnicalAnalysisError(
            f"company {company!r} is not registered; provide an explicit ticker"
        )

    registered_tickers = sorted(
        {str(item).strip().upper() for item in entry.get("tickers", []) if str(item).strip()}
    )
    if ticker:
        selected_ticker = ticker
    elif len(registered_tickers) == 1:
        selected_ticker = registered_tickers[0]
    elif registered_tickers:
        raise TechnicalAnalysisError(
            f"company {entry['canonical_name']} has multiple tickers: "
            f"{', '.join(registered_tickers)}; choose one explicitly"
        )
    else:
        raise TechnicalAnalysisError(f"company {entry['canonical_name']} has no registered ticker")

    report_directory = repo_root / str(entry["directory"])
    base_report = latest_primary_report(report_directory)
    if base_report is None:
        raise TechnicalAnalysisError(
            f"no dated primary research report found in {report_directory.relative_to(repo_root)}"
        )
    base_report_cutoff, base_report_date = report_context_dates(base_report)
    return {
        "company": str(entry["canonical_name"]),
        "ticker": selected_ticker,
        "report_directory": report_directory.relative_to(repo_root).as_posix(),
        "base_report": base_report.relative_to(repo_root).as_posix(),
        "base_report_cutoff": base_report_cutoff.isoformat() if base_report_cutoff else None,
        "base_report_date": base_report_date.isoformat() if base_report_date else None,
        "related_files": referenced_project_files(base_report, repo_root),
    }


def parse_price_band(price_range: str) -> tuple[float, float] | None:
    """Parse one explicit report price band into an inclusive numeric interval."""
    text = str(price_range or "").replace("—", "-").replace("–", "-").strip()
    values = [finite_number(value) for value in PRICE_NUMBER_PATTERN.findall(text)]
    numbers = [value for value in values if value is not None and value >= 0]
    if not numbers:
        return None
    if len(numbers) >= 2:
        return min(numbers[0], numbers[1]), max(numbers[0], numbers[1])
    number = numbers[0]
    if re.search(r"(?:≤|<=|低于|以下|不高于|小于)", text):
        return 0.0, number
    if re.search(r"(?:≥|>=|高于|以上|不低于|大于)", text):
        return number, math.inf
    return number, number


def is_fundamental_entry_action(text: str) -> bool:
    """Return whether an extracted action explicitly permits a new entry."""
    action = str(text or "")
    if re.search(r"不买|不加仓|不宜买|观望|等待|减仓|卖出|回避|持有不加", action):
        return False
    return bool(re.search(r"买入|建仓|加仓|配置|积累", action))


def explicit_narrative_entry_bands(lines: list[str]) -> list[dict[str, Any]]:
    """Extract price bands only from narrative lines that explicitly permit entry."""
    bands: list[dict[str, Any]] = []
    seen: set[tuple[float, float, str]] = set()
    for raw_line in lines:
        line = re.sub(r"[*`_]", "", raw_line).strip()
        if line.startswith(">"):
            line = line[1:].strip()
        if not is_fundamental_entry_action(line):
            continue
        for match in EXPLICIT_PRICE_BAND_PATTERN.finditer(line):
            price_range = match.group(0).strip()
            parsed = parse_price_band(price_range)
            if not parsed:
                continue
            low, high = parsed
            key = (low, high, price_range)
            if key in seen:
                continue
            seen.add(key)
            action = line[: match.start()].strip(" ：:-") or "主报告明确建仓条件"
            bands.append(
                {
                    "price_range": price_range,
                    "low": low,
                    "high": high,
                    "action": action,
                    "rationale": "主报告正文中的明确建仓表述",
                }
            )
    return bands


def fundamental_entry_bands(report_path: Path, market: str) -> list[dict[str, Any]]:
    """Read explicit entry bands from the related report without updating the dashboard."""
    if not report_path.is_file():
        return []
    try:
        import build_investment_dashboard as dashboard

        lines = report_path.read_text(encoding="utf-8", errors="replace").splitlines()
        valuation_section = dashboard.extract_valuation_section(lines)
        valuation_lines = valuation_section["markdown"].splitlines() if valuation_section else lines
        price_plan = dashboard.extract_price_plan(valuation_lines, market=market)
        if not price_plan and valuation_lines is not lines:
            price_plan = dashboard.extract_price_plan(lines, market=market)
    except (ImportError, OSError, ValueError, KeyError, TypeError):
        return []

    if not price_plan:
        return explicit_narrative_entry_bands(lines)

    bands: list[dict[str, Any]] = []
    seen: set[tuple[float, float, str]] = set()
    for item in price_plan:
        action = str(item.get("action") or item.get("profile") or "")
        price_range = str(item.get("price_range") or "")
        parsed = parse_price_band(price_range)
        if not parsed or not is_fundamental_entry_action(action):
            continue
        low, high = parsed
        key = (low, high, price_range)
        if key in seen:
            continue
        seen.add(key)
        bands.append(
            {
                "price_range": price_range,
                "low": low,
                "high": high,
                "action": action,
                "rationale": str(item.get("rationale") or ""),
            }
        )
    return sorted(bands, key=lambda band: (band["high"], band["low"]))


def display_fundamental_entry_bands(bands: list[dict[str, Any]], currency: str) -> str:
    """Format extracted report bands compactly while preserving their original action."""
    if not bands:
        return "主报告未提取到可核验的建仓价格带"
    parts = []
    for band in bands:
        action = re.sub(r"\s+", " ", str(band.get("action") or "建仓候选")).strip()
        price_range = str(band.get("price_range") or "").strip()
        if currency and currency not in price_range and not re.search(r"元|港元|美元|HKD|USD|CNY", price_range, re.I):
            price_range = f"{price_range} {currency}"
        parts.append(f"{action}：{price_range}")
    return "；".join(parts)


def intersect_price_bands(
    fundamental_bands: list[dict[str, Any]],
    technical_zone: dict[str, Any] | None,
) -> list[dict[str, float]]:
    """Return price intersections, if any, between valuation bands and a technical zone."""
    if not technical_zone:
        return []
    technical_low = finite_number(technical_zone.get("low"))
    technical_high = finite_number(technical_zone.get("high"))
    if technical_low is None or technical_high is None:
        return []
    intersections: list[dict[str, float]] = []
    for band in fundamental_bands:
        low = max(float(band["low"]), technical_low)
        high = min(float(band["high"]), technical_high)
        if low <= high:
            intersections.append({"low": rounded(low, 2), "high": rounded(high, 2)})
    return intersections


def display_intersections(intersections: list[dict[str, float]], currency: str) -> str:
    if not intersections:
        return "无交集"
    return "；".join(
        f"{display_number(item['low'])}-{display_number(item['high'])} {currency}"
        for item in intersections
    )


def trend_lights(result: dict[str, Any]) -> list[dict[str, str]]:
    """Translate core timing inputs into readable green/yellow/red signals."""
    latest = result["latest"]
    trend = result["trend"]
    momentum = result["momentum"]
    close = finite_number(latest.get("close"))

    def moving_average_light(
        label: str,
        average_key: str,
        slope_key: str,
        period: str,
    ) -> dict[str, str]:
        average = finite_number(trend.get(average_key))
        slope = str(trend.get(slope_key) or "数据不足")
        if close is None or average is None:
            return {"dimension": label, "light": "黄", "meaning": "均线数据不足，暂不判断。"}
        if close >= average and slope == "上行":
            return {"dimension": label, "light": "绿", "meaning": f"股价在{period}日均线之上，且均线在上行。"}
        if close < average and slope == "下行":
            return {"dimension": label, "light": "红", "meaning": f"股价在{period}日均线之下，且均线在下行。"}
        if close < average:
            return {"dimension": label, "light": "红", "meaning": f"股价仍在{period}日均线之下。"}
        if slope == "下行":
            return {"dimension": label, "light": "黄", "meaning": f"股价暂在{period}日均线之上，但均线仍在下行。"}
        return {"dimension": label, "light": "黄", "meaning": f"股价在{period}日均线附近，趋势尚未充分确认。"}

    lights = [
        moving_average_light("短期（20日）", "sma20", "sma20_slope", "20"),
        moving_average_light("中期（60日）", "sma60", "sma60_slope", "60"),
        moving_average_light("长期（200日）", "sma200", "sma200_slope", "200"),
    ]
    volume_ratio = finite_number(momentum.get("volume_ratio_5_to_20"))
    if volume_ratio is None:
        volume = {"dimension": "量能确认", "light": "黄", "meaning": "成交量数据不足，无法确认资金参与度。"}
    elif volume_ratio >= 1.1:
        volume = {"dimension": "量能确认", "light": "绿", "meaning": "近5日平均成交量高于20日平均，量能有确认。"}
    elif volume_ratio < 0.8:
        volume = {"dimension": "量能确认", "light": "红", "meaning": "近5日平均成交量明显低于20日平均，缺少量能确认。"}
    else:
        volume = {"dimension": "量能确认", "light": "黄", "meaning": "近5日平均成交量接近20日平均，尚无明显放量确认。"}
    return [*lights, volume]


def decision_snapshot(
    result: dict[str, Any],
    fundamental_bands: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine valuation bands and technical conditions without a forecast claim."""
    technical_zone = result["levels"].get("preferred_observation_zone")
    intersections = intersect_price_bands(fundamental_bands, technical_zone)
    quality = result["data_quality"]
    state = str(result["technical_state"])
    if not quality["publishable"]:
        answer = "暂不能判断"
        reason = "行情质量或跨源核验未通过，技术面只可作诊断。"
    elif not fundamental_bands:
        answer = "暂不能判断"
        reason = "主报告未提取到明确且可核验的建仓价格带。"
    elif not intersections:
        answer = "否"
        reason = "基本面允许价位与技术观察区没有重叠。"
    elif state != "关注分批区":
        answer = "否"
        reason = f"价格区间虽有重叠，但当前技术状态为“{state}”，尚未达到分批观察条件。"
    else:
        answer = "是（候选）"
        reason = "基本面允许价位与技术观察区重叠，且技术状态满足分批观察条件；仍需核对主报告的风险红线。"
    return {
        "answer": answer,
        "reason": reason,
        "technical_zone": technical_zone,
        "intersections": intersections,
        "lights": trend_lights(result),
    }


def default_auto_output(
    company: str,
    ticker: str,
    market: str,
    analysis_date: date,
    repo_root: Path = ROOT,
) -> Path:
    """Route an automatic technical report beside the company's research."""
    import report_routing

    filename = f"{company}-technical-analysis-{analysis_date.strftime('%Y%m%d')}.md"
    route = report_routing.resolve_route(
        company=company,
        ticker=ticker,
        market=market,
        report_type="company",
        filename=filename,
        repo_root=repo_root,
        registry=report_routing.load_registry(
            repo_root / "data" / "report-routing" / "company_registry.json"
        ),
        create=True,
    )
    destination = route.get("destination_path")
    if not destination or route.get("status") == "routed_to_inbox":
        raise TechnicalAnalysisError(f"cannot route automatic report: {route.get('reason')}")
    return repo_root / str(destination)


def fetch_yahoo_history(symbol: str, start: date, end: date) -> tuple[list[PriceRow], dict[str, Any]]:
    """Fetch daily OHLCV rows from Yahoo's chart endpoint through ``end``."""
    params = {
        "period1": int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
        "period2": int(
            datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp()
        ),
        "interval": "1d",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    url = f"{YAHOO_CHART_URL.format(symbol=symbol)}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "ai-berkshire-technical-analysis/1.0"})
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed provider endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise TechnicalAnalysisError(f"Yahoo history request failed for {symbol}: {error}") from error

    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise TechnicalAnalysisError(f"Yahoo returned an error for {symbol}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise TechnicalAnalysisError(f"Yahoo returned no history for {symbol}")
    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows: list[PriceRow] = []
    rejected = 0
    for index, timestamp in enumerate(timestamps):
        values = {}
        for field in ("open", "high", "low", "close", "volume"):
            series = quotes.get(field) or []
            values[field] = finite_number(series[index]) if index < len(series) else None
        if any(values[field] is None for field in values):
            rejected += 1
            continue
        if values["close"] <= 0 or values["high"] < values["low"] or values["volume"] < 0:
            rejected += 1
            continue
        rows.append(
            PriceRow(
                trading_date=datetime.fromtimestamp(timestamp, tz=timezone.utc).date(),
                open=values["open"],
                high=values["high"],
                low=values["low"],
                close=values["close"],
                volume=values["volume"],
            )
        )
    metadata = result.get("meta") or {}
    return normalize_rows(rows), {
        "provider": "Yahoo Finance Chart API",
        "provider_symbol": symbol,
        "source_url": url,
        "rejected_rows": rejected,
        "currency": metadata.get("currency"),
        "exchange_timezone": metadata.get("exchangeTimezoneName"),
        "instrument_type": metadata.get("instrumentType"),
    }


def fetch_yahoo_intraday(
    symbol: str,
    start: date,
    end: date,
    interval: str = INTRADAY_INTERVAL,
    market: str | None = None,
) -> tuple[list[PriceRow], dict[str, Any]]:
    """Fetch timestamped intraday OHLCV bars for the independent 30m layer."""
    if interval != INTRADAY_INTERVAL:
        raise TechnicalAnalysisError(f"unsupported intraday interval: {interval}")
    # Yahoo currently rejects a 30m range that reaches beyond its rolling
    # 60-calendar-day window; keep the requested endpoint inclusive while
    # leaving one day of provider-side headroom.
    start = max(start, end - timedelta(days=59))
    params = {
        "period1": int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
        "period2": int(
            datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp()
        ),
        "interval": interval,
        "events": "div,splits",
        "includeAdjustedClose": "true",
        "includePrePost": "false",
    }
    url = f"{YAHOO_CHART_URL.format(symbol=symbol)}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "ai-berkshire-technical-analysis/1.0"})
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed provider endpoint
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise TechnicalAnalysisError(f"Yahoo intraday request failed for {symbol}: {error}") from error

    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise TechnicalAnalysisError(f"Yahoo returned an intraday error for {symbol}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise TechnicalAnalysisError(f"Yahoo returned no intraday history for {symbol}")
    result = results[0]
    metadata = result.get("meta") or {}
    timezone_name = metadata.get("exchangeTimezoneName") or {
        "A股": "Asia/Shanghai",
        "港股": "Asia/Hong_Kong",
    }.get(market or "", "Asia/Shanghai")
    try:
        exchange_timezone = ZoneInfo(str(timezone_name))
    except (KeyError, ValueError):
        exchange_timezone = ZoneInfo("Asia/Shanghai")

    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows: list[PriceRow] = []
    rejected = 0
    for index, timestamp in enumerate(timestamps):
        values = {}
        for field in ("open", "high", "low", "close", "volume"):
            series = quotes.get(field) or []
            values[field] = finite_number(series[index]) if index < len(series) else None
        if any(values[field] is None for field in values):
            rejected += 1
            continue
        if values["close"] <= 0 or values["high"] < values["low"] or values["volume"] <= 0:
            rejected += 1
            continue
        try:
            bar_time = datetime.fromtimestamp(float(timestamp), tz=timezone.utc).astimezone(exchange_timezone)
        except (TypeError, ValueError, OverflowError, OSError):
            rejected += 1
            continue
        rows.append(
            PriceRow(
                trading_date=bar_time.date(),
                open=values["open"],
                high=values["high"],
                low=values["low"],
                close=values["close"],
                volume=values["volume"],
                bar_time=bar_time,
            )
        )
    return normalize_rows(rows), {
        "provider": "Yahoo Finance Chart API",
        "provider_symbol": symbol,
        "source_url": url,
        "interval": interval,
        "rejected_rows": rejected,
        "currency": metadata.get("currency"),
        "exchange_timezone": str(exchange_timezone),
        "instrument_type": metadata.get("instrumentType"),
        "include_prepost": False,
    }


def parse_csv_date(raw: str) -> date:
    value = raw.strip()
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise TechnicalAnalysisError(f"unsupported CSV date: {raw!r}")


def load_csv_history(path: Path) -> tuple[list[PriceRow], dict[str, Any]]:
    """Load a user-supplied OHLCV CSV with case-insensitive headers."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise TechnicalAnalysisError(f"CSV has no header: {path}")
            header_map = {name.strip().casefold(): name for name in reader.fieldnames}
            required = ("date", "open", "high", "low", "close", "volume")
            missing = [name for name in required if name not in header_map]
            if missing:
                raise TechnicalAnalysisError(f"CSV is missing columns: {', '.join(missing)}")
            rows: list[PriceRow] = []
            rejected = 0
            for raw in reader:
                try:
                    values = {name: finite_number(raw[header_map[name]]) for name in required[1:]}
                    if any(value is None for value in values.values()):
                        raise ValueError("non-numeric OHLCV")
                    rows.append(
                        PriceRow(
                            trading_date=parse_csv_date(raw[header_map["date"]]),
                            open=values["open"],
                            high=values["high"],
                            low=values["low"],
                            close=values["close"],
                            volume=values["volume"],
                        )
                    )
                except (KeyError, TypeError, ValueError, TechnicalAnalysisError):
                    rejected += 1
    except OSError as error:
        raise TechnicalAnalysisError(f"cannot read CSV {path}: {error}") from error
    return normalize_rows(rows), {
        "provider": "local CSV",
        "provider_symbol": None,
        "source_url": str(path.resolve()),
        "rejected_rows": rejected,
        "currency": None,
        "exchange_timezone": None,
        "instrument_type": None,
    }


def normalize_rows(rows: Iterable[PriceRow]) -> list[PriceRow]:
    """Sort and de-duplicate daily or timestamped intraday OHLCV rows."""
    by_key: dict[str, PriceRow] = {}
    for row in rows:
        if row.close <= 0 or row.high < row.low or row.volume < 0:
            continue
        key = row.bar_time.isoformat() if row.bar_time else row.trading_date.isoformat()
        by_key[key] = row
    return sorted(
        by_key.values(),
        key=lambda row: (
            row.trading_date,
            row.bar_time or datetime.min.replace(tzinfo=timezone.utc),
        ),
    )


def remove_incomplete_daily_bar(
    rows: list[PriceRow],
    source: dict[str, Any],
    market: str,
    now: datetime | None = None,
) -> list[PriceRow]:
    """Exclude a current-session partial daily bar from canonical daily analysis."""
    if not rows:
        return rows
    timezone_name = source.get("exchange_timezone")
    if not timezone_name:
        return rows
    try:
        local_now = (now or datetime.now().astimezone()).astimezone(ZoneInfo(str(timezone_name)))
    except (KeyError, ValueError):
        return rows
    close_hour = {"A股": 15, "港股": 16, "美股": 16}.get(market)
    if close_hour is None:
        return rows
    finalization_time = local_now.replace(
        hour=close_hour,
        minute=30,
        second=0,
        microsecond=0,
    )
    if rows[-1].trading_date == local_now.date() and local_now < finalization_time:
        source["incomplete_rows_removed"] = int(source.get("incomplete_rows_removed", 0)) + 1
        return rows[:-1]
    return rows


def get_talib() -> Any:
    """Import the pinned indicator engine and reject incompatible versions."""
    try:
        import talib  # type: ignore
    except ImportError as error:
        raise TechnicalAnalysisError(
            "TA-Lib is required. Install it with: python3 -m pip install -r requirements-technical.txt"
        ) from error
    version = str(getattr(talib, "__version__", "unknown"))
    if version != "0.7.1":
        raise TechnicalAnalysisError(f"TA-Lib 0.7.1 is required for reproducibility; found {version}")
    return talib


def last_finite(values: Any, offset: int = 0) -> float | None:
    """Return the last finite array item before an optional offset."""
    stop = len(values) - offset
    for index in range(stop - 1, -1, -1):
        number = finite_number(values[index])
        if number is not None:
            return number
    return None


def rounded(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def pct_distance(value: float, anchor: float | None) -> float | None:
    if anchor is None or anchor == 0:
        return None
    return (value / anchor - 1) * 100


def slope_label(current: float | None, prior: float | None, tolerance: float = 0.001) -> str:
    if current is None or prior is None or prior == 0:
        return "数据不足"
    change = current / prior - 1
    if change > tolerance:
        return "上行"
    if change < -tolerance:
        return "下行"
    return "走平"


def tencent_cross_check(ticker: str, market: str, latest: PriceRow) -> dict[str, Any]:
    """Cross-check the latest A/H close against Tencent's independent quote."""
    if market not in {"A股", "港股"}:
        return {"status": "not_available", "reason": "Tencent check is limited to A/H shares"}
    try:
        import market_snapshot

        symbol = market_snapshot.tencent_symbol(ticker, market)
        if not symbol:
            return {"status": "not_available", "reason": "ticker cannot be mapped to Tencent"}
        metadata = {symbol: {"ticker": ticker, "market": market, "company": ticker}}
        quotes = market_snapshot.fetch_quotes(metadata)
        if not quotes:
            return {"status": "unavailable", "reason": "Tencent returned no quote"}
        quote = quotes[0]
        provider_timestamp = str(quote.get("provider_timestamp") or "")
        provider_date = (
            datetime.strptime(provider_timestamp[:8], "%Y%m%d").date()
            if re.fullmatch(r"20\d{12}", provider_timestamp)
            else None
        )
        candidates = [
            ("current_price", finite_number(quote.get("price"))),
            ("previous_close", finite_number(quote.get("previous_close"))),
        ]
        candidates = [(kind, price) for kind, price in candidates if price is not None and price > 0]
        if provider_date:
            preferred_kind = "current_price" if latest.trading_date == provider_date else "previous_close"
            candidates.sort(key=lambda item: 0 if item[0] == preferred_kind else 1)
        else:
            candidates.sort(key=lambda item: abs(latest.close / item[1] - 1))
        if candidates:
            reference_kind, reference_price = candidates[0]
        else:
            reference_kind, reference_price = "unavailable", None
        if reference_price is None or reference_price <= 0:
            return {"status": "unavailable", "reason": "Tencent quote has no comparable price"}
        difference_pct = abs(latest.close / reference_price - 1) * 100
        return {
            "status": "verified" if difference_pct <= CROSS_SOURCE_TOLERANCE_PCT else "mismatch",
            "provider": "Tencent quote",
            "reference_kind": reference_kind,
            "reference_price": rounded(reference_price),
            "historical_close": rounded(latest.close),
            "difference_pct": rounded(difference_pct),
            "tolerance_pct": CROSS_SOURCE_TOLERANCE_PCT,
            "provider_timestamp": provider_timestamp or None,
        }
    except Exception as error:
        return {"status": "unavailable", "reason": str(error)}


def derive_timing_state(
    *,
    close: float,
    sma20: float | None,
    sma60: float | None,
    sma200: float | None,
    rsi14: float | None,
    atr14: float | None,
    sma20_slope: str,
    sma60_slope: str,
    observations: int,
) -> tuple[str, str]:
    """Classify timing conservatively without pretending to predict returns."""
    if observations < MINIMUM_OBSERVATIONS or sma200 is None or atr14 is None or rsi14 is None:
        return "数据不足", "历史样本不足以形成完整的长期趋势与波动判断。"
    if close < sma200 or (sma60 is not None and close < sma60 and sma60_slope == "下行"):
        return "防守观察", "价格位于长期趋势线下方或中期趋势转弱，不提供建仓买点。"
    distance_to_sma20_atr = (close - sma20) / atr14 if sma20 is not None and atr14 > 0 else None
    if rsi14 >= 70 or (distance_to_sma20_atr is not None and distance_to_sma20_atr >= 2.0):
        return "等待回踩", "中长期趋势未必转坏，但短期价格偏离均值较大，避免追高。"
    near_trend = False
    for average in (sma20, sma60):
        if average is not None and atr14 > 0 and abs(close - average) <= atr14:
            near_trend = True
    if close > sma200 and sma20_slope == "上行" and sma60_slope in {"上行", "走平"} and near_trend:
        if 35 <= rsi14 <= 65:
            return "关注分批区", "趋势仍在且价格靠近中期均值，可结合基本面价格纪律观察分批买点。"
    if close > sma200 and sma60 is not None and close > sma60:
        return "趋势确认", "中长期趋势为正，但当前位置没有形成足够明确的回踩买点。"
    return "中性观察", "指标没有形成一致的趋势或位置优势，等待更清晰的价格结构。"


def price_zone(anchor: float | None, atr: float | None) -> dict[str, float] | None:
    if anchor is None or atr is None or anchor <= 0 or atr <= 0:
        return None
    return {"low": rounded(max(0, anchor - 0.5 * atr), 2), "high": rounded(anchor + 0.5 * atr, 2)}


def compute_analysis(
    rows: list[PriceRow],
    *,
    company: str,
    ticker: str,
    yahoo_symbol: str,
    market: str,
    as_of: date,
    source: dict[str, Any],
    cross_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute a structured technical snapshot using the pinned TA-Lib engine."""
    if len(rows) < 60:
        raise TechnicalAnalysisError(f"at least 60 valid trading rows are required; found {len(rows)}")
    rows = [row for row in rows if row.trading_date <= as_of]
    if len(rows) < 60:
        raise TechnicalAnalysisError(f"fewer than 60 rows remain at cutoff {as_of.isoformat()}")
    latest = rows[-1]
    staleness_days = (as_of - latest.trading_date).days
    if staleness_days < 0:
        raise TechnicalAnalysisError("latest price is after the requested cutoff")

    talib = get_talib()
    try:
        import numpy as np  # type: ignore
    except ImportError as error:
        raise TechnicalAnalysisError("NumPy is required by TA-Lib") from error

    high = np.asarray([row.high for row in rows], dtype="float64")
    low = np.asarray([row.low for row in rows], dtype="float64")
    close = np.asarray([row.close for row in rows], dtype="float64")
    volume = np.asarray([row.volume for row in rows], dtype="float64")
    sma20_series = talib.SMA(close, timeperiod=20)
    sma60_series = talib.SMA(close, timeperiod=60)
    sma200_series = talib.SMA(close, timeperiod=200)
    rsi_series = talib.RSI(close, timeperiod=14)
    atr_series = talib.ATR(high, low, close, timeperiod=14)
    macd_series, macd_signal_series, macd_hist_series = talib.MACD(
        close, fastperiod=12, slowperiod=26, signalperiod=9
    )
    bb_upper_series, bb_middle_series, bb_lower_series = talib.BBANDS(
        close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
    )
    adx_series = talib.ADX(high, low, close, timeperiod=14)

    sma20 = last_finite(sma20_series)
    sma60 = last_finite(sma60_series)
    sma200 = last_finite(sma200_series)
    atr14 = last_finite(atr_series)
    rsi14 = last_finite(rsi_series)
    sma20_slope = slope_label(sma20, last_finite(sma20_series, offset=5))
    sma60_slope = slope_label(sma60, last_finite(sma60_series, offset=5))
    sma200_slope = slope_label(sma200, last_finite(sma200_series, offset=5))
    timing_state, timing_reason = derive_timing_state(
        close=latest.close,
        sma20=sma20,
        sma60=sma60,
        sma200=sma200,
        rsi14=rsi14,
        atr14=atr14,
        sma20_slope=sma20_slope,
        sma60_slope=sma60_slope,
        observations=len(rows),
    )

    rolling_20_high = max(row.high for row in rows[-20:])
    rolling_20_low = min(row.low for row in rows[-20:])
    rolling_60_high = max(row.high for row in rows[-60:])
    rolling_60_low = min(row.low for row in rows[-60:])
    volume_5 = sum(row.volume for row in rows[-5:]) / min(5, len(rows))
    volume_20 = sum(row.volume for row in rows[-20:]) / min(20, len(rows))
    volume_ratio = volume_5 / volume_20 if volume_20 > 0 else None
    if cross_check is not None:
        check = cross_check
    elif abs((date.today() - latest.trading_date).days) <= MAX_STALENESS_DAYS:
        check = tencent_cross_check(ticker, market, latest)
    else:
        check = {
            "status": "not_available",
            "reason": "historical cutoff is outside the latest-quote verification window",
        }

    quality_warnings: list[str] = []
    if len(rows) < MINIMUM_OBSERVATIONS:
        quality_warnings.append(f"仅有 {len(rows)} 个有效交易日，少于长期趋势最低要求 {MINIMUM_OBSERVATIONS}。")
    elif len(rows) < PREFERRED_OBSERVATIONS:
        quality_warnings.append(f"仅有 {len(rows)} 个有效交易日，长期均线缓冲样本有限。")
    if staleness_days > MAX_STALENESS_DAYS:
        quality_warnings.append(f"最新行情距分析截止日 {staleness_days} 天，超过允许的 {MAX_STALENESS_DAYS} 天。")
    if source.get("rejected_rows"):
        quality_warnings.append(f"数据清洗剔除了 {source['rejected_rows']} 行不完整或非法行情。")
    if source.get("incomplete_rows_removed"):
        quality_warnings.append("已剔除交易时段内尚未完成的当日日线，避免用半日成交量计算指标。")
    if check.get("status") == "mismatch":
        quality_warnings.append(
            f"Yahoo 与腾讯价格偏差 {check.get('difference_pct')}%，超过 {CROSS_SOURCE_TOLERANCE_PCT}% 容差。"
        )
    if check.get("status") in {"unavailable", "not_available"}:
        quality_warnings.append("最新价格未完成独立行情源交叉验证。")

    publishable = (
        len(rows) >= MINIMUM_OBSERVATIONS
        and staleness_days <= MAX_STALENESS_DAYS
        and check.get("status") != "mismatch"
    )
    if publishable and check.get("status") == "verified" and len(rows) >= PREFERRED_OBSERVATIONS:
        confidence = "高"
    elif publishable:
        confidence = "中"
    else:
        confidence = "低"
        if timing_state != "数据不足":
            timing_state = "数据待复核"
            timing_reason = "行情质量或跨源核验未通过，暂不输出可执行买点。"

    ma20_zone = price_zone(sma20, atr14)
    ma60_zone = price_zone(sma60, atr14)
    preferred_zone = None
    candidate_zones = [zone for zone in (ma20_zone, ma60_zone) if zone and zone["low"] <= latest.close]
    if candidate_zones:
        preferred_zone = min(candidate_zones, key=lambda item: abs(latest.close - item["high"]))

    return {
        "schema_version": 1,
        "report_type": "technical-analysis",
        "company": company,
        "ticker": ticker,
        "provider_symbol": yahoo_symbol,
        "market": market,
        "analysis_date": date.today().isoformat(),
        "requested_cutoff": as_of.isoformat(),
        "data_cutoff": latest.trading_date.isoformat(),
        "observations": len(rows),
        "engine": {"name": "TA-Lib", "version": str(talib.__version__)},
        "source": source,
        "cross_check": check,
        "data_quality": {
            "publishable": publishable,
            "confidence": confidence,
            "staleness_days": staleness_days,
            "warnings": quality_warnings,
        },
        "latest": {
            "close": rounded(latest.close),
            "open": rounded(latest.open),
            "high": rounded(latest.high),
            "low": rounded(latest.low),
            "volume": rounded(latest.volume, 0),
            "currency": source.get("currency"),
        },
        "trend": {
            "sma20": rounded(sma20),
            "sma60": rounded(sma60),
            "sma200": rounded(sma200),
            "sma20_slope": sma20_slope,
            "sma60_slope": sma60_slope,
            "sma200_slope": sma200_slope,
            "distance_to_sma20_pct": rounded(pct_distance(latest.close, sma20)),
            "distance_to_sma60_pct": rounded(pct_distance(latest.close, sma60)),
            "distance_to_sma200_pct": rounded(pct_distance(latest.close, sma200)),
            "adx14": rounded(last_finite(adx_series)),
        },
        "momentum": {
            "rsi14": rounded(rsi14),
            "macd": rounded(last_finite(macd_series)),
            "macd_signal": rounded(last_finite(macd_signal_series)),
            "macd_histogram": rounded(last_finite(macd_hist_series)),
            "volume_ratio_5_to_20": rounded(volume_ratio),
        },
        "volatility": {
            "atr14": rounded(atr14),
            "atr_pct": rounded(atr14 / latest.close * 100) if atr14 else None,
            "bollinger_upper": rounded(last_finite(bb_upper_series)),
            "bollinger_middle": rounded(last_finite(bb_middle_series)),
            "bollinger_lower": rounded(last_finite(bb_lower_series)),
        },
        "levels": {
            "rolling_20_high": rounded(rolling_20_high),
            "rolling_20_low": rounded(rolling_20_low),
            "rolling_60_high": rounded(rolling_60_high),
            "rolling_60_low": rounded(rolling_60_low),
            "ma20_atr_zone": ma20_zone,
            "ma60_atr_zone": ma60_zone,
            "preferred_observation_zone": preferred_zone,
        },
        "technical_state": timing_state,
        "technical_reason": timing_reason,
    }


def _intraday_light(light: str, meaning: str) -> dict[str, str]:
    return {"light": light, "meaning": meaning}


def _intraday_session_stats(rows: list[PriceRow], latest_date: date) -> dict[str, float | None]:
    """Return session VWAP, opening range, and same-slot relative volume."""
    session_rows = [row for row in rows if row.trading_date == latest_date and row.bar_time]
    if not session_rows:
        return {
            "vwap": None,
            "opening_range_high": None,
            "opening_range_low": None,
            "relative_volume": None,
        }
    total_volume = sum(row.volume for row in session_rows)
    vwap = (
        sum(((row.high + row.low + row.close) / 3) * row.volume for row in session_rows) / total_volume
        if total_volume > 0
        else None
    )
    opening_rows = session_rows[:2]
    latest = session_rows[-1]
    slot = (latest.bar_time.hour, latest.bar_time.minute) if latest.bar_time else None
    prior_slot_volumes = [
        row.volume
        for row in rows
        if row.trading_date < latest_date
        and row.bar_time
        and slot is not None
        and (row.bar_time.hour, row.bar_time.minute) == slot
    ][-20:]
    baseline = sum(prior_slot_volumes) / len(prior_slot_volumes) if prior_slot_volumes else None
    return {
        "vwap": vwap,
        "opening_range_high": max(row.high for row in opening_rows),
        "opening_range_low": min(row.low for row in opening_rows),
        "relative_volume": latest.volume / baseline if baseline and baseline > 0 else None,
    }


def compute_intraday_analysis(
    rows: list[PriceRow],
    *,
    company: str,
    ticker: str,
    yahoo_symbol: str,
    market: str,
    as_of: date,
    source: dict[str, Any],
    cross_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute an independent 30-minute timing snapshot.

    This layer is deliberately not compatible with the daily decision contract:
    it describes session rhythm and entry timing only, and is attached to the
    dashboard as an auxiliary observation.
    """
    rows = [row for row in normalize_rows(rows) if row.bar_time and row.trading_date <= as_of]
    if not rows:
        raise TechnicalAnalysisError("no valid timestamped intraday rows remain at the requested cutoff")

    latest = rows[-1]
    staleness_days = (as_of - latest.trading_date).days
    warnings: list[str] = []
    if len(rows) < INTRADAY_MINIMUM_OBSERVATIONS:
        warnings.append(
            f"仅有 {len(rows)} 个有效30分钟K线，少于最低要求 {INTRADAY_MINIMUM_OBSERVATIONS}。"
        )
    elif len(rows) < INTRADAY_PREFERRED_OBSERVATIONS:
        warnings.append(
            f"仅有 {len(rows)} 个有效30分钟K线，低于建议样本 {INTRADAY_PREFERRED_OBSERVATIONS}。"
        )
    if staleness_days > MAX_STALENESS_DAYS:
        warnings.append(f"最新30分钟K线距请求截止日 {staleness_days} 天，超过允许的 {MAX_STALENESS_DAYS} 天。")
    if source.get("rejected_rows"):
        warnings.append(f"数据清洗剔除了 {source['rejected_rows']} 行不完整或非法30分钟行情。")

    if len(rows) < INTRADAY_MINIMUM_OBSERVATIONS:
        return {
            "schema_version": 1,
            "report_type": "technical-intraday",
            "analysis_mode": "intraday_30m",
            "company": company,
            "ticker": ticker,
            "provider_symbol": yahoo_symbol,
            "market": market,
            "interval": INTRADAY_INTERVAL,
            "analysis_date": as_of.isoformat(),
            "requested_cutoff": as_of.isoformat(),
            "data_cutoff": latest.trading_date.isoformat(),
            "bar_timestamp": latest.bar_time.isoformat() if latest.bar_time else None,
            "observations": len(rows),
            "engine": {"name": "TA-Lib", "version": "0.7.1"},
            "status": "review",
            "publishable": False,
            "technical_state": "数据不足",
            "technical_reason": "30分钟样本不足，不能稳定计算盘中辅助指标。",
            "confidence": "低",
            "latest": {"close": rounded(latest.close), "currency": source.get("currency")},
            "trend": {},
            "momentum": {},
            "volatility": {},
            "intraday": {},
            "lights": [],
            "cross_check": cross_check or {"status": "not_available"},
            "source": source,
            "warnings": warnings,
        }

    talib = get_talib()
    try:
        import numpy as np  # type: ignore
    except ImportError as error:
        raise TechnicalAnalysisError("NumPy is required by TA-Lib") from error

    high = np.asarray([row.high for row in rows], dtype="float64")
    low = np.asarray([row.low for row in rows], dtype="float64")
    close = np.asarray([row.close for row in rows], dtype="float64")
    volume = np.asarray([row.volume for row in rows], dtype="float64")
    ema9_series = talib.EMA(close, timeperiod=9)
    ema20_series = talib.EMA(close, timeperiod=20)
    ema60_series = talib.EMA(close, timeperiod=60)
    ema200_series = talib.EMA(close, timeperiod=200)
    rsi_series = talib.RSI(close, timeperiod=14)
    atr_series = talib.ATR(high, low, close, timeperiod=14)
    macd_series, macd_signal_series, macd_hist_series = talib.MACD(
        close, fastperiod=12, slowperiod=26, signalperiod=9
    )
    bb_upper_series, bb_middle_series, bb_lower_series = talib.BBANDS(
        close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
    )
    adx_series = talib.ADX(high, low, close, timeperiod=14)

    ema9 = last_finite(ema9_series)
    ema20 = last_finite(ema20_series)
    ema60 = last_finite(ema60_series)
    ema200 = last_finite(ema200_series)
    rsi14 = last_finite(rsi_series)
    atr14 = last_finite(atr_series)
    ema20_slope = slope_label(ema20, last_finite(ema20_series, offset=5))
    ema60_slope = slope_label(ema60, last_finite(ema60_series, offset=5))
    session = _intraday_session_stats(rows, latest.trading_date)
    distance_to_ema20_atr = (latest.close - ema20) / atr14 if ema20 and atr14 and atr14 > 0 else None
    if ema60 is None or atr14 is None or rsi14 is None:
        technical_state = "数据不足"
        technical_reason = "30分钟指标尚未形成足够的有效窗口。"
    elif latest.close < ema60 and ema60_slope == "下行":
        technical_state = "防守观察"
        technical_reason = "盘中价格位于EMA60下方且中期盘中趋势下行，只观察，不追价。"
    elif rsi14 >= 70 or (distance_to_ema20_atr is not None and distance_to_ema20_atr >= 1.5):
        technical_state = "等待回踩"
        technical_reason = "盘中价格短线偏热或明显偏离EMA20，等待回踩确认。"
    elif (
        latest.close > ema60
        and ema20_slope == "上行"
        and distance_to_ema20_atr is not None
        and abs(distance_to_ema20_atr) <= 1.0
        and 35 <= rsi14 <= 65
    ):
        technical_state = "关注分批区"
        technical_reason = "盘中趋势向上，价格靠近EMA20且动量未过热，可作为分批节奏观察。"
    elif latest.close > ema60:
        technical_state = "趋势确认"
        technical_reason = "盘中价格站在EMA60上方，但尚未形成明确的回踩节奏。"
    else:
        technical_state = "中性观察"
        technical_reason = "盘中指标没有形成一致的趋势与位置优势，等待更清晰结构。"

    atr_pct = atr14 / latest.close * 100 if atr14 and latest.close else None
    relative_volume = session["relative_volume"]
    lights = [
        {
            "dimension": "EMA趋势",
            **_intraday_light(
                "绿" if latest.close > (ema20 or latest.close) and ema20_slope == "上行"
                else "红" if ema60 is not None and latest.close < ema60
                else "黄",
                "观察价格与EMA20/EMA60及其斜率，不替代日线趋势。",
            ),
        },
        {
            "dimension": "动量",
            **_intraday_light(
                "绿" if rsi14 is not None and 45 <= rsi14 <= 65 and (last_finite(macd_hist_series) or 0) >= 0
                else "红" if rsi14 is not None and (rsi14 < 30 or rsi14 > 75)
                else "黄",
                "RSI14与MACD柱只用于识别盘中过热、过弱或动量配合。",
            ),
        },
        {
            "dimension": "波动",
            **_intraday_light(
                "红" if atr_pct is not None and atr_pct >= 5 else "绿" if atr_pct is not None and atr_pct <= 2 else "黄",
                "ATR14衡量30分钟正常波动幅度，波动越大越需要降低追价冲动。",
            ),
        },
        {
            "dimension": "盘中量价",
            **_intraday_light(
                "绿" if relative_volume is not None and 0.9 <= relative_volume <= 1.8
                else "红" if relative_volume is not None and relative_volume < 0.5
                else "黄",
                "相对量能按同一盘中时间段对比近20个交易日，避免把早盘天然放量误判成异动。",
            ),
        },
    ]
    publishable = (
        len(rows) >= INTRADAY_MINIMUM_OBSERVATIONS
        and ema200 is not None
        and staleness_days <= MAX_STALENESS_DAYS
    )
    confidence = "高" if publishable and len(rows) >= INTRADAY_PREFERRED_OBSERVATIONS else "中" if publishable else "低"
    if not publishable:
        technical_state = "数据待复核"
        technical_reason = "盘中数据新鲜度或样本质量未达到发布条件，只保留诊断信息。"

    return {
        "schema_version": 1,
        "report_type": "technical-intraday",
        "analysis_mode": "intraday_30m",
        "company": company,
        "ticker": ticker,
        "provider_symbol": yahoo_symbol,
        "market": market,
        "interval": INTRADAY_INTERVAL,
        "analysis_date": as_of.isoformat(),
        "requested_cutoff": as_of.isoformat(),
        "data_cutoff": latest.trading_date.isoformat(),
        "bar_timestamp": latest.bar_time.isoformat() if latest.bar_time else None,
        "observations": len(rows),
        "engine": {"name": "TA-Lib", "version": str(talib.__version__)},
        "status": "ready" if publishable else "review",
        "publishable": publishable,
        "technical_state": technical_state,
        "technical_reason": technical_reason,
        "confidence": confidence,
        "latest": {
            "open": rounded(latest.open),
            "high": rounded(latest.high),
            "low": rounded(latest.low),
            "close": rounded(latest.close),
            "volume": rounded(latest.volume, 0),
            "currency": source.get("currency"),
        },
        "trend": {
            "ema9": rounded(ema9),
            "ema20": rounded(ema20),
            "ema60": rounded(ema60),
            "ema200": rounded(ema200),
            "ema20_slope": ema20_slope,
            "ema60_slope": ema60_slope,
            "adx14": rounded(last_finite(adx_series)),
        },
        "momentum": {
            "rsi14": rounded(rsi14),
            "macd": rounded(last_finite(macd_series)),
            "macd_signal": rounded(last_finite(macd_signal_series)),
            "macd_histogram": rounded(last_finite(macd_hist_series)),
        },
        "volatility": {
            "atr14": rounded(atr14),
            "atr_pct": rounded(atr_pct),
            "bollinger_upper": rounded(last_finite(bb_upper_series)),
            "bollinger_middle": rounded(last_finite(bb_middle_series)),
            "bollinger_lower": rounded(last_finite(bb_lower_series)),
        },
        "intraday": {
            "vwap": rounded(session["vwap"]),
            "relative_volume": rounded(relative_volume),
            "opening_range_high": rounded(session["opening_range_high"]),
            "opening_range_low": rounded(session["opening_range_low"]),
        },
        "lights": lights,
        "cross_check": cross_check or {
            "status": "not_available",
            "reason": "30分钟盘中快照不与收盘日线交叉核验，当前只作为独立节奏观察。",
        },
        "source": source,
        "warnings": warnings,
    }


def display_number(value: Any, digits: int = 2) -> str:
    number = finite_number(value)
    if number is None:
        return "数据不足"
    return f"{number:,.{digits}f}"


def display_zone(zone: dict[str, Any] | None) -> str:
    if not zone:
        return "数据不足"
    return f"{display_number(zone.get('low'))}-{display_number(zone.get('high'))}"


def yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def render_markdown(
    result: dict[str, Any],
    base_report: str | None = None,
    base_report_cutoff: str | None = None,
    base_report_date: str | None = None,
    related_files: list[str] | None = None,
    fundamental_bands: list[dict[str, Any]] | None = None,
) -> str:
    """Render a decision-first, stable technical report contract."""
    latest = result["latest"]
    trend = result["trend"]
    momentum = result["momentum"]
    volatility = result["volatility"]
    levels = result["levels"]
    quality = result["data_quality"]
    source = result["source"]
    check = result["cross_check"]
    cutoff_label = "最近一个完整日线"
    currency = latest.get("currency") or {"A股": "CNY", "港股": "HKD", "美股": "USD"}.get(result["market"], "")
    preferred_zone = display_zone(levels.get("preferred_observation_zone"))
    fundamental_bands = fundamental_bands or []
    decision = decision_snapshot(result, fundamental_bands)
    fundamental_summary = display_fundamental_entry_bands(fundamental_bands, currency)
    technical_zone = display_zone(decision["technical_zone"])
    combined_zone = display_intersections(decision["intersections"], currency)
    lines = [
        "---",
        'type: "technical-analysis"',
        f"company: {yaml_string(result['company'])}",
        f"ticker: {yaml_string(result['ticker'])}",
        f"market: {yaml_string(result['market'])}",
        f"analysis_date: {yaml_string(result['analysis_date'])}",
        'analysis_mode: "daily_close"',
        f"requested_cutoff: {yaml_string(result['requested_cutoff'])}",
        f"data_cutoff: {yaml_string(result['data_cutoff'])}",
        f"technical_state: {yaml_string(result['technical_state'])}",
        f"technical_confidence: {yaml_string(quality['confidence'])}",
        f"publishable: {'true' if quality['publishable'] else 'false'}",
        f"latest_price: {latest['close']}",
        f"currency: {yaml_string(currency)}",
        f"preferred_observation_zone: {yaml_string(preferred_zone)}",
        f"fundamental_entry_plan: {yaml_string(fundamental_summary)}",
        f"combined_candidate_zone: {yaml_string(combined_zone)}",
        f"valid_buy_candidate: {yaml_string(decision['answer'])}",
    ]
    if base_report:
        lines.append(f"base_report: {yaml_string(base_report)}")
    if base_report_cutoff:
        lines.append(f"base_report_cutoff: {yaml_string(base_report_cutoff)}")
    if base_report_date:
        lines.append(f"base_report_date: {yaml_string(base_report_date)}")
    lines.extend(
        [
            "---",
            "",
            f"# {result['company']}（{result['ticker']}）技术面辅助报告",
            "",
            f"> 执行日期：{result['analysis_date']}  ",
            f"> 技术分析请求截止：{result['requested_cutoff']}  ",
            f"> 技术指标行情截止：{result['data_cutoff']}（{cutoff_label}）  ",
            f"> 指标引擎：TA-Lib {result['engine']['version']}  ",
            f"> 数据来源：{source.get('provider')}（{source.get('provider_symbol') or '本地文件'}）  ",
            "> 定位：只辅助判断建仓节奏，不评价公司质量或内在价值，不构成投资建议。",
            "",
            "## 先看结论",
            "",
            "| 问题 | 当前答案 |",
            "|---|---|",
            f"| 当前存在有效买入候选区吗 | **{decision['answer']}** |",
            f"| 主报告允许的建仓价位 | {fundamental_summary} |",
            f"| 技术观察区（不是买入区） | {technical_zone} {currency} |",
            f"| 基本面与技术面的重合区 | {combined_zone} |",
            f"| 当前技术状态 | {result['technical_state']} |",
            f"| 为什么 | {decision['reason']} |",
            "",
            "## 三盏趋势灯",
            "",
            "| 观察维度 | 信号 | 直白解释 |",
            "|---|---|---|",
        ]
    )
    lines.extend(
        f"| {light['dimension']} | {light['light']} | {light['meaning']} |"
        for light in decision["lights"]
    )
    lines.extend(
        [
            "",
            "## 下次重点看什么",
            "",
            "- 先等价格进入主报告明确允许的建仓价位；技术观察区本身不能替代估值纪律。",
            "- 入区后，再确认技术状态是否为“关注分批区”；这代表价格靠近中期均值、短期均线向上且中长期趋势没有转弱。",
            "- 量能由黄或红转绿会增强确认，但不单独构成买入理由。",
            "",
            "## 数据质量",
            "",
            "| 项目 | 结果 |",
            "|---|---|",
            f"| 有效交易日 | {result['observations']} |",
            f"| 可发布 | {'是' if quality['publishable'] else '否'} |",
            f"| 技术面置信度 | {quality['confidence']}（数据与计算质量，不代表预测准确率） |",
            f"| 行情新鲜度 | 距请求截止日 {quality['staleness_days']} 天 |",
            f"| 跨源核验 | {check.get('status', 'not_available')}"
            + (f"，偏差 {check.get('difference_pct')}%" if check.get("difference_pct") is not None else "")
            + " |",
        ]
    )
    if quality["warnings"]:
        lines.extend(["", "数据注意事项（是否阻断以“可发布”字段为准）："])
        lines.extend(f"- {warning}" for warning in quality["warnings"])
    else:
        lines.extend(["", "数据质量检查未发现阻断项。"])

    if base_report:
        lines.extend(
            [
                "",
                "## 关联研究上下文",
                "",
                f"- 最新基本面主报告：`{base_report}`",
            ]
        )
        if base_report_cutoff or base_report_date:
            context_dates = []
            if base_report_cutoff:
                context_dates.append(f"数据截止 {base_report_cutoff}")
            if base_report_date:
                context_dates.append(f"报告日期 {base_report_date}")
            lines.append(
                f"- 基本面报告日期：{'；'.join(context_dates)}。"
                "该日期只用于选择和关联主报告，不作为技术行情截止日。"
            )
        if related_files:
            lines.append("- 主报告引用的项目文件：")
            lines.extend(f"  - `{path}`" for path in related_files)
        else:
            lines.append("- 主报告未引用其他可解析的项目本地文件。")
        lines.append("- 上述文件只建立研究关联，不参与 TA-Lib 指标计算。")

    lines.extend(
        [
            "",
            "## 指标明细与复核",
            "",
            "| 维度 | 指标 | 当前值 | 解释 |",
            "|---|---|---:|---|",
            f"| 价格 | 收盘价 | {display_number(latest['close'])} {currency} | 行情截止日收盘/最新可得价 |",
            f"| 趋势 | SMA20 | {display_number(trend['sma20'])} | {trend['sma20_slope']}，距现价 {display_number(trend['distance_to_sma20_pct'])}% |",
            f"| 趋势 | SMA60 | {display_number(trend['sma60'])} | {trend['sma60_slope']}，距现价 {display_number(trend['distance_to_sma60_pct'])}% |",
            f"| 趋势 | SMA200 | {display_number(trend['sma200'])} | {trend['sma200_slope']}，距现价 {display_number(trend['distance_to_sma200_pct'])}% |",
            f"| 趋势强度 | ADX14 | {display_number(trend['adx14'])} | 只衡量趋势强弱，不判断方向 |",
            f"| 动量 | RSI14 | {display_number(momentum['rsi14'])} | 高于70偏热，低于30偏弱，不单独作为反转信号 |",
            f"| 动量 | MACD柱 | {display_number(momentum['macd_histogram'], 4)} | 正值代表短期动量高于信号线 |",
            f"| 量能 | 5日/20日均量 | {display_number(momentum['volume_ratio_5_to_20'])}x | 高于1表示近期量能高于20日均值 |",
            f"| 波动 | ATR14 | {display_number(volatility['atr14'])}（{display_number(volatility['atr_pct'])}%） | 用于估计正常日线波动，不是止损价 |",
            "",
            "## 技术观察区的计算",
            "",
            f"**技术状态：{result['technical_state']}**（技术观察区不等于买入区）",
            "",
            result["technical_reason"],
            "",
            "| 参考区域 | 区间 | 计算口径 |",
            "|---|---:|---|",
            f"| 优先观察区 | {preferred_zone} {currency} | 最接近现价的 SMA20/SMA60，向上下各扩展 0.5×ATR |",
            f"| SMA20 波动带 | {display_zone(levels.get('ma20_atr_zone'))} {currency} | SMA20 ± 0.5×ATR |",
            f"| SMA60 波动带 | {display_zone(levels.get('ma60_atr_zone'))} {currency} | SMA60 ± 0.5×ATR |",
            f"| 20日价格区间 | {display_number(levels['rolling_20_low'])}-{display_number(levels['rolling_20_high'])} {currency} | 近20个交易日最低/最高价 |",
            f"| 60日价格区间 | {display_number(levels['rolling_60_low'])}-{display_number(levels['rolling_60_high'])} {currency} | 近60个交易日最低/最高价 |",
            "",
            "## 使用边界",
            "",
            "- 只有基本面与估值已经通过时，技术状态才可用于安排首笔或分批节奏。",
            "- RSI、MACD、均线和成交量都是滞后统计，不提供确定性预测，也不应单独触发买入。",
            "- 本 Skill 的时点规则尚未完成可复现的全市场、多周期回测；不提供胜率、准确率或超额收益承诺。",
            "- 除权、拆股、停牌、流动性不足和单一行情源异常会破坏可比性；“可发布=否”时不执行买点建议。",
            "- 技术状态随每日价格变化，后续报告覆盖的是技术快照，不覆盖原基本面结论。",
            "",
            "## 来源与复核",
            "",
            f"- 历史行情：{source.get('provider')}，代码 `{source.get('provider_symbol') or result['ticker']}`。",
            f"- 指标计算：TA-Lib {result['engine']['version']}。",
            f"- 跨源价格：{check.get('provider', '未获得独立来源')}，状态 `{check.get('status', 'not_available')}`。",
            "",
        ]
    )
    return "\n".join(lines)


def write_output(path: Path, content: str, force: bool = False) -> None:
    if path.exists() and not force:
        raise TechnicalAnalysisError(f"output already exists: {path}; pass --force to overwrite intentionally")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ticker",
        nargs="?",
        help="optional project ticker; omit it to resolve from --company",
    )
    parser.add_argument("--company", required=True, help="company display name")
    parser.add_argument("--market", help="A股, 港股, 美股, or another display market")
    parser.add_argument("--as-of", help="analysis cutoff YYYY-MM-DD; defaults to today")
    parser.add_argument("--lookback-days", type=int, default=900, help="calendar days to fetch (default: 900)")
    parser.add_argument("--csv", type=Path, help="use a local OHLCV CSV instead of Yahoo")
    parser.add_argument("--base-report", help="relative path to the related fundamental report")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path, help="write output to this path")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output intentionally")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        as_of = parse_iso_date(arguments.as_of) if arguments.as_of else date.today()
        project_context = None
        company = arguments.company
        ticker_input = arguments.ticker
        if ticker_input is None:
            project_context = resolve_project_context(company)
            company = project_context["company"]
            ticker_input = project_context["ticker"]
        else:
            try:
                project_context = resolve_project_context(company, ticker_input)
                company = project_context["company"]
            except TechnicalAnalysisError:
                project_context = None

        ticker, yahoo_symbol, market = normalize_ticker(ticker_input, arguments.market)
        base_report = arguments.base_report or (project_context or {}).get("base_report")
        base_report_path = Path(base_report) if base_report else None
        if base_report_path and not base_report_path.is_absolute():
            base_report_path = ROOT / base_report_path
        fundamental_bands = (
            fundamental_entry_bands(base_report_path, market) if base_report_path else []
        )
        if arguments.csv:
            rows, source = load_csv_history(arguments.csv.resolve())
        else:
            start = as_of - timedelta(days=max(arguments.lookback_days, 365))
            rows, source = fetch_yahoo_history(yahoo_symbol, start, as_of)
        rows = remove_incomplete_daily_bar(rows, source, market)
        rows = [row for row in rows if row.trading_date <= as_of]
        if not rows:
            raise TechnicalAnalysisError("no valid rows are available at the requested cutoff")
        result = compute_analysis(
            rows,
            company=company,
            ticker=ticker,
            yahoo_symbol=yahoo_symbol,
            market=market,
            as_of=as_of,
            source=source,
        )
        result["analysis_mode"] = "daily_close"
        content = (
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if arguments.format == "json"
            else render_markdown(
                result,
                base_report=base_report,
                base_report_cutoff=(project_context or {}).get("base_report_cutoff"),
                base_report_date=(project_context or {}).get("base_report_date"),
                related_files=(project_context or {}).get("related_files"),
                fundamental_bands=fundamental_bands,
            )
        )
        output_path = arguments.output.resolve() if arguments.output else None
        if output_path is None and arguments.ticker is None and arguments.format == "markdown":
            output_path = default_auto_output(company, ticker, market, date.today())
        if output_path:
            write_output(output_path, content, force=arguments.force)
            print(output_path)
        else:
            print(content, end="" if content.endswith("\n") else "\n")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, TechnicalAnalysisError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
