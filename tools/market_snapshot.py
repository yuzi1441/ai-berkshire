#!/usr/bin/env python3
"""Refresh quote snapshots for the static dashboard.

The command reads tickers from the generated decision board. It queries Tencent
quotes only during the relevant weekday trading sessions unless ``--force`` is
used. A-share indices are fetched alongside A-share stocks and are kept in a
separate ``indices`` array. The output is a separate market snapshot, never an
edit to report text or report-derived recommendation fields.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import re
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
QUOTE_URL = "https://qt.gtimg.cn/q="
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")

A_SHARE_INDICES: tuple[dict[str, str], ...] = (
    {"index_id": "sse", "ticker": "000001.SH", "symbol": "sh000001", "name": "上证指数"},
    {"index_id": "szse", "ticker": "399001.SZ", "symbol": "sz399001", "name": "深证成指"},
    {"index_id": "chinext", "ticker": "399006.SZ", "symbol": "sz399006", "name": "创业板指"},
    {"index_id": "star50", "ticker": "000688.SH", "symbol": "sh000688", "name": "科创50"},
    {"index_id": "hs300", "ticker": "000300.SH", "symbol": "sh000300", "name": "沪深300"},
    {"index_id": "csi500", "ticker": "000905.SH", "symbol": "sh000905", "name": "中证500"},
    {"index_id": "csi1000", "ticker": "000852.SH", "symbol": "sh000852", "name": "中证1000"},
)


def is_in_range(current: time, start: time, end: time) -> bool:
    """Return whether a local time falls inside an inclusive trading interval."""
    return start <= current <= end


def is_market_open(market: str, now: datetime) -> bool:
    """Return whether a supported market is in a standard weekday session.

    Exchange holiday calendars are not bundled with the repository. A provider
    response of no quote is retained as an unavailable snapshot rather than
    fabricated as a tradable quote.
    """
    local_now = now.astimezone(SHANGHAI_TIMEZONE)
    if local_now.weekday() >= 5:
        return False
    current = local_now.time().replace(tzinfo=None)
    if market == "A股":
        return is_in_range(current, time(9, 30), time(11, 30)) or is_in_range(
            current, time(13, 0), time(15, 0)
        )
    if market == "港股":
        return is_in_range(current, time(9, 30), time(12, 0)) or is_in_range(
            current, time(13, 0), time(16, 0)
        )
    return False


def tencent_symbol(ticker: str, market: str) -> str | None:
    """Convert a normalized board ticker into Tencent's quote symbol format."""
    raw = ticker.strip().upper()
    if raw.endswith(".HK") or market == "港股":
        code = raw.removesuffix(".HK")
        return f"hk{code.zfill(5)}" if code.isdigit() else None
    if raw.endswith(".SH"):
        return f"sh{raw.removesuffix('.SH')}"
    if raw.endswith(".SZ"):
        return f"sz{raw.removesuffix('.SZ')}"
    if raw.endswith(".BJ"):
        return f"bj{raw.removesuffix('.BJ')}"
    if raw.isdigit() and len(raw) == 6:
        return f"sh{raw}" if raw.startswith(("6", "9")) else f"sz{raw}"
    return None


def quote_currency(market: str) -> str:
    """Return the standard display currency for a supported market."""
    return "HKD" if market == "港股" else "CNY"


def parse_tencent_payload(payload: str, symbols: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """Parse Tencent's tilde-delimited quote response into stable JSON fields."""
    quotes: list[dict[str, Any]] = []
    for symbol, metadata in symbols.items():
        match = re.search(rf'v_{re.escape(symbol)}="([^"]*)"', payload)
        if not match:
            continue
        fields = match.group(1).split("~")
        if len(fields) < 5:
            continue
        try:
            price = float(fields[3])
            previous_close = float(fields[4])
        except ValueError:
            continue
        if price <= 0:
            continue
        provider_timestamp = next(
            (
                field
                for field in reversed(fields)
                if re.fullmatch(r"20\d{12}", field)
                or re.fullmatch(r"20\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", field)
            ),
            None,
        )
        if provider_timestamp and "/" in provider_timestamp:
            data_cutoff = provider_timestamp[:10].replace("/", "-")
        elif provider_timestamp:
            data_cutoff = f"{provider_timestamp[:4]}-{provider_timestamp[4:6]}-{provider_timestamp[6:8]}"
        else:
            data_cutoff = None
        change_pct = None
        if previous_close > 0:
            change_pct = round((price - previous_close) / previous_close * 100, 4)
        provider_pct = None
        if len(fields) > 32:
            try:
                candidate = float(fields[32])
                if abs(candidate) < 50:
                    provider_pct = candidate
            except ValueError:
                provider_pct = None
        if provider_pct is not None:
            change_pct = provider_pct
        quotes.append(
            {
                "ticker": metadata["ticker"],
                "market": metadata["market"],
                "symbol": symbol,
                "name": fields[1] or metadata["company"],
                "kind": metadata.get("kind", "stock"),
                "index_id": metadata.get("index_id"),
                "price": price,
                "previous_close": previous_close,
                "change_pct": change_pct,
                "currency": quote_currency(metadata["market"]),
                "provider_timestamp": provider_timestamp,
                "data_cutoff": data_cutoff,
                "source": "Tencent quote",
            }
        )
    return quotes


def load_watchlist(
    board_path: Path, markets: set[str] | None = None
) -> dict[str, dict[str, str]]:
    """Build a de-duplicated Tencent symbol map from current A/H decisions."""
    with board_path.open(encoding="utf-8") as handle:
        board = json.load(handle)
    symbols: dict[str, dict[str, str]] = {}
    for item in board.get("decisions", []):
        ticker = item.get("ticker")
        market = item.get("market")
        if not ticker or market not in (markets or {"A股", "港股"}):
            continue
        symbol = tencent_symbol(str(ticker), str(market))
        if symbol:
            symbols[symbol] = {
                "ticker": str(ticker),
                "market": str(market),
                "company": str(item.get("company", ticker)),
                "kind": "stock",
            }
    return symbols


def load_index_watchlist() -> dict[str, dict[str, str]]:
    """Return the fixed A-share index universe tracked by the dashboard."""
    return {
        item["symbol"]: {
            "ticker": item["ticker"],
            "market": "A股",
            "company": item["name"],
            "kind": "index",
            "index_id": item["index_id"],
        }
        for item in A_SHARE_INDICES
    }


def fetch_quotes(symbols: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """Fetch Tencent quotes in bounded batches without third-party packages."""
    quotes: list[dict[str, Any]] = []
    symbol_list = list(symbols)
    for start in range(0, len(symbol_list), 50):
        batch = symbol_list[start : start + 50]
        request = Request(
            f"{QUOTE_URL}{','.join(batch)}",
            headers={"User-Agent": "ai-berkshire-investment-dashboard/1.0"},
        )
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed provider URL
            payload = response.read().decode("gb18030", errors="replace")
        quotes.extend(parse_tencent_payload(payload, {symbol: symbols[symbol] for symbol in batch}))
    return quotes


def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    """Write a UTF-8 quote snapshot and create its parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextmanager
def snapshot_mutation_lock(path: Path):
    """Serialize read/merge/write mutations of one shared A/H snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_snapshot(path: Path) -> dict[str, Any] | None:
    """Load a prior snapshot only when it contains a structurally usable quote list."""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("quotes"), list):
        return None
    return payload


def _quote_dates(quotes: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(item.get("data_cutoff"))
            for item in quotes
            if isinstance(item, dict) and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(item.get("data_cutoff") or ""))
        }
    )


def _quote_phase(checked_at: datetime, active_markets: set[str], quotes: list[dict[str, Any]]) -> str:
    """Classify a quote snapshot without treating a closed market as missing data."""
    if active_markets:
        return "intraday"
    dates = _quote_dates(quotes)
    if dates and dates[-1] == checked_at.date().isoformat():
        return "close"
    return "historical_close"


def _market_session(market: str, checked_at: datetime) -> str:
    local = checked_at.astimezone(SHANGHAI_TIMEZONE)
    if local.weekday() >= 5:
        return "non_trading_day"
    current = local.time().replace(tzinfo=None)
    if is_market_open(market, local):
        return "trading"
    if current < time(9, 30):
        return "pre_open"
    if market == "A股" and time(11, 30) < current < time(13, 0):
        return "midday_break"
    if market == "港股" and time(12, 0) < current < time(13, 0):
        return "midday_break"
    return "closed"


def _market_quote_type(market: str, checked_at: datetime, quotes: list[dict[str, Any]]) -> str:
    dates = _quote_dates(quotes)
    if not dates or dates[-1] != checked_at.date().isoformat():
        return "historical_close"
    return "close" if _market_session(market, checked_at) == "closed" else "intraday"


def _legacy_market_snapshot(payload: dict[str, Any], market: str) -> dict[str, Any]:
    market_quotes = [item for item in payload.get("quotes", []) if item.get("market") == market]
    if not market_quotes:
        return {}
    return {
        "market": market,
        "quote_type": payload.get("quote_phase") or "historical_close",
        "session": "unknown",
        "source_status": payload.get("source_status") or "unknown",
        "refresh_status": "legacy_snapshot",
        "data_cutoff": max(_quote_dates(market_quotes), default=None),
        "last_attempted_at": payload.get("last_attempted_at") or payload.get("generated_at"),
        "last_success_at": payload.get("generated_at"),
        "tracked_count": len(market_quotes),
        "quote_count": len(market_quotes),
    }


def _market_snapshots(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stored = payload.get("market_snapshots")
    result = dict(stored) if isinstance(stored, dict) else {}
    for market in ("A股", "港股"):
        if market not in result:
            legacy = _legacy_market_snapshot(payload, market)
            if legacy:
                result[market] = legacy
    return result


def _combined_quote_phase(markets: dict[str, dict[str, Any]]) -> str:
    phases = {str(item.get("quote_type") or "") for item in markets.values() if item}
    if "intraday" in phases:
        return "intraday"
    if "close" in phases:
        return "close"
    return "historical_close"


def _write_site_snapshot(board_path: Path, output_path: Path, snapshot: dict[str, Any]) -> None:
    repo_root = board_path.resolve().parents[2]
    site_snapshot = repo_root / "site" / "data" / "quotes" / "latest.json"
    if output_path.resolve() != site_snapshot.resolve():
        write_snapshot(site_snapshot, snapshot)


def refresh_snapshot(
    board_path: Path,
    output_path: Path,
    now: datetime | None = None,
    force: bool = False,
    markets: set[str] | None = None,
) -> dict[str, Any]:
    """Refresh the snapshot if any requested market is currently open."""
    checked_at = (now or datetime.now().astimezone()).astimezone(SHANGHAI_TIMEZONE)
    requested_markets = markets or {"A股", "港股"}
    symbols = load_watchlist(board_path, requested_markets)
    if "A股" in requested_markets:
        symbols.update(load_index_watchlist())
    active_markets = {metadata["market"] for metadata in symbols.values() if is_market_open(metadata["market"], checked_at)}
    if not force and not active_markets:
        return {
            "updated": False,
            "reason": "outside_standard_trading_session",
            "checked_at": checked_at.isoformat(),
            "requested_markets": sorted(requested_markets),
        }

    active_symbols = {
        symbol: metadata
        for symbol, metadata in symbols.items()
        if force or metadata["market"] in active_markets
    }
    all_stock_symbols = load_watchlist(board_path, {"A股", "港股"})
    previous = load_snapshot(output_path)
    try:
        quotes = fetch_quotes(active_symbols)
    except (OSError, UnicodeError, ValueError) as error:
        with snapshot_mutation_lock(output_path):
            latest = load_snapshot(output_path) or previous
            if latest and latest.get("quotes"):
                preserved = dict(latest)
                markets_payload = _market_snapshots(preserved)
                for market in requested_markets:
                    prior = dict(markets_payload.get(market) or {"market": market})
                    prior.update({
                        "session": _market_session(market, checked_at),
                        "refresh_status": "failed",
                        "source_status": "unavailable",
                        "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                        "source_error": str(error)[:300],
                    })
                    markets_payload[market] = prior
                preserved.update({
                    "market_snapshots": markets_payload,
                    "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                    "source_status": "partial",
                    "source_error": str(error)[:300],
                })
                write_snapshot(output_path, preserved)
                _write_site_snapshot(board_path, output_path, preserved)
                return {"updated": False, "reason": "provider_unavailable_preserved_previous", **preserved}
            failed = {
                "schema_version": 1,
                "generated_at": checked_at.isoformat(timespec="seconds"),
                "market_status": "trading_session" if active_markets else "forced_refresh",
                "quote_phase": "historical_close",
                "source_status": "unavailable",
                "data_cutoff": None,
                "requested_markets": sorted(requested_markets),
                "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                "tracked_count": len(all_stock_symbols),
                "quote_count": 0,
                "quotes": [],
                "index_tracked_count": len(A_SHARE_INDICES),
                "index_count": 0,
                "indices": [],
                "market_snapshots": {
                    market: {
                        "market": market,
                        "quote_type": "historical_close",
                        "session": _market_session(market, checked_at),
                        "source_status": "unavailable",
                        "refresh_status": "failed",
                        "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                        "last_success_at": None,
                        "tracked_count": sum(
                            item.get("market") == market for item in all_stock_symbols.values()
                        ),
                        "quote_count": 0,
                        "source_error": str(error)[:300],
                    }
                    for market in requested_markets
                },
                "source_error": str(error)[:300],
            }
            write_snapshot(output_path, failed)
            _write_site_snapshot(board_path, output_path, failed)
        return {
            **failed,
            "updated": False,
            "reason": "provider_unavailable",
            "source_status": "unavailable",
        }
    fresh_stock_quotes = [quote for quote in quotes if quote.get("kind") != "index"]
    fresh_index_quotes = [quote for quote in quotes if quote.get("kind") == "index"]
    with snapshot_mutation_lock(output_path):
        latest = load_snapshot(output_path) or previous or {"quotes": [], "indices": []}
        combined_quotes = list(latest.get("quotes") or [])
        combined_indices = list(latest.get("indices") or [])
        markets_payload = _market_snapshots(latest)
        any_updated = False
        failed_markets: list[str] = []
        for market in requested_markets:
            if not force and market not in active_markets:
                continue
            expected = sum(
                item.get("kind") != "index" and item.get("market") == market
                for item in active_symbols.values()
            )
            market_quotes = [item for item in fresh_stock_quotes if item.get("market") == market]
            previous_market_quotes = [
                item for item in combined_quotes if item.get("market") == market
            ]
            prior = dict(markets_payload.get(market) or {"market": market})
            if not market_quotes:
                failed_markets.append(market)
                prior.update({
                    "session": _market_session(market, checked_at),
                    "refresh_status": "failed",
                    "source_status": "unavailable",
                    "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                    "source_error": "quote provider returned no stock quotes",
                })
                markets_payload[market] = prior
                continue
            any_updated = True
            combined_quotes = [item for item in combined_quotes if item.get("market") != market]
            fresh_tickers = {str(item.get("ticker") or "") for item in market_quotes}
            market_quotes = [dict(item, snapshot_status="current") for item in market_quotes]
            preserved_missing = [
                dict(item, snapshot_status="preserved_previous")
                for item in previous_market_quotes
                if str(item.get("ticker") or "") not in fresh_tickers
            ]
            combined_quotes.extend([*market_quotes, *preserved_missing])
            if market == "A股":
                combined_indices = fresh_index_quotes
            status = "ok" if len(market_quotes) == expected else "partial"
            data_dates = _quote_dates(market_quotes)
            markets_payload[market] = {
                "market": market,
                "quote_type": _market_quote_type(market, checked_at, market_quotes),
                "session": _market_session(market, checked_at),
                "source": "Tencent quote",
                "source_status": status,
                "refresh_status": "success" if status == "ok" else "partial",
                "data_cutoff": data_dates[-1] if data_dates else None,
                "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                "last_success_at": checked_at.isoformat(timespec="seconds"),
                "tracked_count": expected,
                "quote_count": len(market_quotes),
            }
        combined_quotes.sort(key=lambda item: str(item.get("ticker") or ""))
        full_tracked_count = len(all_stock_symbols)
        has_partial_market = any(
            item.get("source_status") != "ok"
            for item in markets_payload.values()
            if isinstance(item, dict)
        )
        source_status = (
            "unavailable"
            if not combined_quotes
            else "partial"
            if failed_markets or has_partial_market or len(combined_quotes) != full_tracked_count
            else "ok"
        )
        data_dates = _quote_dates(combined_quotes)
        snapshot = {
            "schema_version": 1,
            "generated_at": checked_at.isoformat(timespec="seconds"),
            "market_status": "trading_session" if active_markets else "forced_refresh",
            "quote_phase": _combined_quote_phase(markets_payload),
            "source_status": source_status,
            "data_cutoff": data_dates[-1] if data_dates else None,
            "requested_markets": sorted(requested_markets),
            "last_attempted_at": checked_at.isoformat(timespec="seconds"),
            "tracked_count": full_tracked_count,
            "quote_count": len(combined_quotes),
            "quotes": combined_quotes,
            "index_tracked_count": len(A_SHARE_INDICES),
            "index_count": len(combined_indices),
            "indices": combined_indices,
            "market_snapshots": markets_payload,
        }
        if failed_markets:
            snapshot["source_error"] = "no stock quotes for: " + ", ".join(sorted(failed_markets))
        write_snapshot(output_path, snapshot)
        _write_site_snapshot(board_path, output_path, snapshot)
    if not any_updated:
        return {"updated": False, "reason": "provider_returned_no_quotes_preserved_previous", **snapshot}
    return {"updated": True, **snapshot}


def main() -> int:
    """Run the market snapshot CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--markets",
        default="A股,港股",
        help="comma-separated markets; use A股 for the unified A-share scheduler",
    )
    parser.add_argument("--force", action="store_true", help="refresh even outside the regular session")
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    requested_markets = {item.strip() for item in arguments.markets.split(",") if item.strip()}
    unsupported = requested_markets - {"A股", "港股"}
    if unsupported:
        parser.error(f"unsupported market(s): {', '.join(sorted(unsupported))}")
    try:
        result = refresh_snapshot(
            repo_root / "data" / "investment-dashboard" / "decision_board.json",
            repo_root / "data" / "investment-dashboard" / "quotes" / "latest.json",
            force=arguments.force,
            markets=requested_markets,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if result["updated"]:
        print(
            f"Updated {result['quote_count']} of {result['tracked_count']} stock quotes and "
            f"{result.get('index_count', 0)} of {result.get('index_tracked_count', 0)} A-share indices."
        )
    else:
        print(f"Skipped refresh: {result['reason']}.")
    return 2 if result.get("source_status") == "unavailable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
