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
            (field for field in reversed(fields) if re.fullmatch(r"20\d{12}", field)),
            None,
        )
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
                "data_cutoff": (
                    f"{provider_timestamp[:4]}-{provider_timestamp[4:6]}-{provider_timestamp[6:8]}"
                    if provider_timestamp
                    else None
                ),
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
    previous = load_snapshot(output_path)
    try:
        quotes = fetch_quotes(active_symbols)
    except (OSError, UnicodeError, ValueError) as error:
        if previous and previous.get("quotes"):
            preserved = dict(previous)
            preserved.update(
                {
                    "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                    "source_status": "unavailable",
                    "source_error": str(error)[:300],
                }
            )
            write_snapshot(output_path, preserved)
            _write_site_snapshot(board_path, output_path, preserved)
            return {"updated": False, "reason": "provider_unavailable_preserved_previous", **preserved}
        return {
            "updated": False,
            "reason": "provider_unavailable",
            "source_status": "unavailable",
            "source_error": str(error)[:300],
            "checked_at": checked_at.isoformat(timespec="seconds"),
            "requested_markets": sorted(requested_markets),
        }
    stock_quotes = [quote for quote in quotes if quote.get("kind") != "index"]
    index_quotes = [quote for quote in quotes if quote.get("kind") == "index"]
    if not stock_quotes and previous and previous.get("quotes"):
        preserved = dict(previous)
        preserved.update(
            {
                "last_attempted_at": checked_at.isoformat(timespec="seconds"),
                "source_status": "unavailable",
                "source_error": "quote provider returned no stock quotes",
            }
        )
        write_snapshot(output_path, preserved)
        _write_site_snapshot(board_path, output_path, preserved)
        return {"updated": False, "reason": "provider_returned_no_quotes_preserved_previous", **preserved}
    tracked_count = len([item for item in active_symbols.values() if item.get("kind") != "index"])
    index_tracked_count = len([item for item in active_symbols.values() if item.get("kind") == "index"])
    source_status = "ok" if len(stock_quotes) == tracked_count else "partial" if stock_quotes else "unavailable"
    data_dates = _quote_dates(stock_quotes)
    snapshot = {
        "schema_version": 1,
        "generated_at": checked_at.isoformat(timespec="seconds"),
        "market_status": "trading_session" if active_markets else "forced_refresh",
        "quote_phase": _quote_phase(checked_at, active_markets, stock_quotes),
        "source_status": source_status,
        "data_cutoff": data_dates[-1] if data_dates else None,
        "requested_markets": sorted(requested_markets),
        "last_attempted_at": checked_at.isoformat(timespec="seconds"),
        "tracked_count": tracked_count,
        "quote_count": len(stock_quotes),
        "quotes": stock_quotes,
        "index_tracked_count": index_tracked_count,
        "index_count": len(index_quotes),
        "indices": index_quotes,
    }
    write_snapshot(output_path, snapshot)
    # Keep the static site payload in sync for local preview and VPS serving.
    _write_site_snapshot(board_path, output_path, snapshot)
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
