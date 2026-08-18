#!/usr/bin/env python3
"""Refresh A-share and Hong Kong quote snapshots for the static dashboard.

The command reads tickers from the generated decision board. It queries Tencent
quotes only during the relevant weekday trading sessions unless ``--force`` is
used. The output is a separate market snapshot, never an edit to report text or
report-derived recommendation fields.
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
                "price": price,
                "previous_close": previous_close,
                "change_pct": change_pct,
                "currency": quote_currency(metadata["market"]),
                "provider_timestamp": provider_timestamp,
                "source": "Tencent quote",
            }
        )
    return quotes


def load_watchlist(board_path: Path) -> dict[str, dict[str, str]]:
    """Build a de-duplicated Tencent symbol map from current A/H decisions."""
    with board_path.open(encoding="utf-8") as handle:
        board = json.load(handle)
    symbols: dict[str, dict[str, str]] = {}
    for item in board.get("decisions", []):
        ticker = item.get("ticker")
        market = item.get("market")
        if not ticker or market not in {"A股", "港股"}:
            continue
        symbol = tencent_symbol(str(ticker), str(market))
        if symbol:
            symbols[symbol] = {
                "ticker": str(ticker),
                "market": str(market),
                "company": str(item.get("company", ticker)),
            }
    return symbols


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh_snapshot(
    board_path: Path,
    output_path: Path,
    now: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Refresh the snapshot if any tracked A/H market is currently open."""
    checked_at = (now or datetime.now().astimezone()).astimezone(SHANGHAI_TIMEZONE)
    symbols = load_watchlist(board_path)
    active_markets = {metadata["market"] for metadata in symbols.values() if is_market_open(metadata["market"], checked_at)}
    if not force and not active_markets:
        return {"updated": False, "reason": "outside_standard_trading_session", "checked_at": checked_at.isoformat()}

    active_symbols = {
        symbol: metadata
        for symbol, metadata in symbols.items()
        if force or metadata["market"] in active_markets
    }
    quotes = fetch_quotes(active_symbols)
    snapshot = {
        "schema_version": 1,
        "generated_at": checked_at.isoformat(timespec="seconds"),
        "market_status": "trading_session" if active_markets else "forced_refresh",
        "tracked_count": len(active_symbols),
        "quote_count": len(quotes),
        "quotes": quotes,
    }
    write_snapshot(output_path, snapshot)
    # Keep the static site payload in sync for local preview and VPS serving.
    site_snapshot = ROOT / "site" / "data" / "quotes" / "latest.json"
    if output_path.resolve() != site_snapshot.resolve():
        write_snapshot(site_snapshot, snapshot)
    return {"updated": True, **snapshot}


def main() -> int:
    """Run the market snapshot CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true", help="refresh even outside the regular session")
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    try:
        result = refresh_snapshot(
            repo_root / "data" / "investment-dashboard" / "decision_board.json",
            repo_root / "data" / "investment-dashboard" / "quotes" / "latest.json",
            force=arguments.force,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if result["updated"]:
        print(f"Updated {result['quote_count']} of {result['tracked_count']} A/H quotes.")
    else:
        print(f"Skipped refresh: {result['reason']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
