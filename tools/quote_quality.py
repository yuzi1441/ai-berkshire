"""Shared quote eligibility with exchange sessions, including holidays/breaks.

The browser only expires this read model; it does not invent its own calendar.
An unavailable/out-of-range calendar fails closed without changing source prices.
"""
from __future__ import annotations

import copy
import math
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
EXCHANGES = {"A股": "XSHG", "港股": "XHKG"}


def observed_at(quote: dict[str, Any]) -> datetime | None:
    value = str(quote.get("provider_timestamp") or "").strip()
    for pattern in ("%Y%m%d%H%M%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=SHANGHAI)
        except ValueError:
            pass
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except ValueError:
        return None


@lru_cache(maxsize=16)
def exchange_calendar(market: str, year: int):
    import exchange_calendars
    # Explicit range: library default end dates must not silently truncate us.
    return exchange_calendars.get_calendar(EXCHANGES[market], start=f"{year-1}-01-01",
                                           end=f"{year}-12-31")


def session_window(market: str, current: datetime) -> tuple[datetime, datetime, datetime, datetime]:
    """Return last session open, required observation time, close, expiry."""
    local = current.astimezone(SHANGHAI)
    calendar = exchange_calendar(market, local.year)
    session = calendar.date_to_session(local.date().isoformat(), direction="previous")
    opening = calendar.session_open(session).to_pydatetime()
    if current < opening:
        session = calendar.previous_session(session)
        opening = calendar.session_open(session).to_pydatetime()
    closing = calendar.session_close(session).to_pydatetime()
    next_open = calendar.session_open(calendar.next_session(session)).to_pydatetime()
    required = min(current, closing)
    expiry = next_open if current >= closing else current + timedelta(minutes=10)
    start = calendar.session_break_start(session)
    end = calendar.session_break_end(session)
    if not str(start) == "NaT" and not str(end) == "NaT":
        start, end = start.to_pydatetime(), end.to_pydatetime()
        if start <= current < end:
            required, expiry = start, end
    return opening, required, closing, expiry


def quote_quality(quote: dict[str, Any] | None, evaluated_at: datetime) -> dict[str, Any]:
    current = evaluated_at.replace(tzinfo=SHANGHAI) if evaluated_at.tzinfo is None else evaluated_at
    result = {"eligible": False, "reason": "quote_missing", "observed_at": None,
              "evaluated_at": current.isoformat(), "valid_until": None,
              "calendar_source": "exchange-calendars"}
    if not isinstance(quote, dict):
        return result
    price = quote.get("price")
    try:
        if isinstance(price, bool) or price is None or not math.isfinite(float(price)) or float(price) <= 0:
            return result
    except (ValueError, TypeError):
        return result
    observed = observed_at(quote)
    result["observed_at"] = observed.isoformat() if observed else None
    metadata = quote.get("_market_snapshot")
    reason = None
    if quote.get("snapshot_status") == "preserved_previous":
        reason = "quote_missing_from_latest_refresh"
    elif quote.get("status") in {"error", "failed", "stale"}:
        reason = "quote_source_unavailable"
    elif not isinstance(metadata, dict):
        reason = "quote_metadata_missing"
    elif metadata.get("refresh_status") == "failed" or metadata.get("source_status") in {"unavailable", "error", "failed"}:
        reason = "market_refresh_failed"
    elif observed is None:
        reason = "quote_timestamp_missing"
    elif observed > current + timedelta(minutes=2):
        reason = "quote_timestamp_in_future"
    if reason:
        result["reason"] = reason
        return result
    market = str(quote.get("market") or metadata.get("market") or "")
    cutoff = str(quote.get("data_cutoff") or metadata.get("data_cutoff") or "")
    if cutoff != observed.astimezone(SHANGHAI).date().isoformat():
        result["reason"] = "quote_date_mismatch"
        return result
    try:
        opening, required, closing, expiry = session_window(market, current)
    except (ImportError, KeyError, ValueError, IndexError, OverflowError):
        result["reason"] = "market_calendar_unavailable"
        return result
    if observed.astimezone(SHANGHAI).date() != opening.astimezone(SHANGHAI).date():
        result["reason"] = "quote_not_latest_trading_session"
        return result
    if observed < opening or observed < required - timedelta(minutes=10):
        result["reason"] = "quote_stale_for_market_session"
        return result
    if required == current and current < closing:
        expiry = min(expiry, observed + timedelta(minutes=10))
    result.update(eligible=True, reason="quote_current_for_market_session", valid_until=expiry.isoformat())
    return result


def with_quote_metadata(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    markets = payload.get("market_snapshots") or {}
    for row in payload.get("quotes", []):
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        quote = dict(row)
        quote["_market_snapshot"] = markets.get(row.get("market")) or {
            "market": row.get("market"), "source_status": payload.get("source_status"),
            "refresh_status": "legacy_snapshot", "data_cutoff": payload.get("data_cutoff"),
        }
        result[str(row["ticker"]).upper()] = quote
    return result


def annotate_snapshot(payload: dict[str, Any], *, evaluated_at: datetime | None = None) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    current = evaluated_at or datetime.now(SHANGHAI)
    quotes = with_quote_metadata(result)
    for row in result.get("quotes", []):
        if isinstance(row, dict):
            row["quality"] = quote_quality(quotes.get(str(row.get("ticker", "")).upper()), current)
    result["quality_evaluated_at"] = current.isoformat()
    return result
