#!/usr/bin/env python3
"""Refresh the independent 30-minute technical layer without rewriting reports."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INTRADAY_MARKET = "A股"
sys.path.insert(0, str(ROOT / "tools"))

import technical_analysis as technical  # noqa: E402
from batch_technical_analysis import load_decisions, load_exclusions  # noqa: E402


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from error


def fetch_intraday_with_retry(
    symbol: str,
    start: date,
    end: date,
    market: str,
    attempts: int,
) -> tuple[list[technical.PriceRow], dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return technical.fetch_yahoo_intraday(
                symbol,
                start,
                end,
                interval=technical.INTRADAY_INTERVAL,
                market=market,
            )
        except technical.TechnicalAnalysisError as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def generate_one(
    decision: dict[str, Any],
    *,
    as_of: date,
    attempts: int,
    lookback_days: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    company = str(decision["company"])
    project_ticker, yahoo_symbol, market = technical.normalize_ticker(
        str(decision["ticker"]), str(decision["market"])
    )
    rows, source = fetch_intraday_with_retry(
        yahoo_symbol,
        as_of - timedelta(days=max(lookback_days, technical.INTRADAY_LOOKBACK_DAYS)),
        as_of,
        market,
        attempts,
    )
    result = technical.compute_intraday_analysis(
        rows,
        company=company,
        ticker=project_ticker,
        yahoo_symbol=yahoo_symbol,
        market=market,
        as_of=as_of,
        source=source,
    )
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return result


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--markets",
        default=INTRADAY_MARKET,
        help="comma-separated markets; 30分钟技术面目前只覆盖A股",
    )
    parser.add_argument("--as-of", type=parse_iso_date, default=date.today())
    parser.add_argument("--lookback-days", type=int, default=technical.INTRADAY_LOOKBACK_DAYS)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "intraday_technical.json",
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.attempts < 1 or arguments.lookback_days < 1:
        print("error: --attempts and --lookback-days must be positive", file=sys.stderr)
        return 2
    repo_root = arguments.repo_root.resolve()
    requested_markets = [item.strip() for item in arguments.markets.split(",") if item.strip()]
    if not requested_markets:
        print("error: at least one market is required", file=sys.stderr)
        return 2
    unsupported_markets = [market for market in requested_markets if market != INTRADAY_MARKET]
    if unsupported_markets:
        print(
            "warning: 30分钟技术面仅覆盖A股，已跳过：" + ", ".join(sorted(set(unsupported_markets))),
            file=sys.stderr,
        )
    markets = [market for market in requested_markets if market == INTRADAY_MARKET]
    if not markets:
        print("error: 30分钟技术面仅支持 --markets A股", file=sys.stderr)
        return 2

    decisions: list[dict[str, Any]] = []
    for market in markets:
        decisions.extend(load_decisions(repo_root, market))
    exclusions = load_exclusions(repo_root)
    selected = [item for item in decisions if str(item["company"]) not in exclusions]
    state_path = repo_root / "data" / "investment-dashboard" / "company_state.json"
    if state_path.is_file():
        try:
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state_payload = {}
        state_by_ticker = {
            str(item.get("ticker") or "").upper(): item
            for item in state_payload.get("companies", [])
            if isinstance(item, dict) and item.get("ticker")
        }
        selected = [
            item
            for item in selected
            if (
                state_by_ticker.get(str(item.get("ticker") or "").upper(), {}).get("lifecycle") == "PRE_BUY"
                and state_by_ticker.get(str(item.get("ticker") or "").upper(), {}).get("technical", {}).get("intraday_eligible") is True
            )
        ]
    if arguments.limit is not None:
        selected = selected[: max(arguments.limit, 0)]

    started = time.perf_counter()
    companies: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, decision in enumerate(selected, start=1):
        company = str(decision["company"])
        ticker = str(decision["ticker"])
        try:
            result = generate_one(
                decision,
                as_of=arguments.as_of,
                attempts=arguments.attempts,
                lookback_days=arguments.lookback_days,
            )
            companies.append(result)
            print(
                f"[{index}/{len(selected)}] {company} {ticker}: "
                f"{result['technical_state']}, 30m {result['data_cutoff']}"
            )
        except (OSError, ValueError, json.JSONDecodeError, technical.TechnicalAnalysisError) as error:
            failures.append(
                {
                    "company": company,
                    "ticker": ticker,
                    "market": decision.get("market"),
                    "status": "failed",
                    "error": str(error),
                }
            )
            print(f"[{index}/{len(selected)}] {company} {ticker}: FAILED {error}", file=sys.stderr)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "analysis_date": arguments.as_of.isoformat(),
        "requested_cutoff": arguments.as_of.isoformat(),
        "interval": technical.INTRADAY_INTERVAL,
        "requested_markets": requested_markets,
        "markets": markets,
        "status": "ok" if not failures else "partial" if companies else "failed",
        "company_count": len(companies),
        "selected_count": len(selected),
        "excluded_count": len(decisions) - len(selected),
        "failed_count": len(failures),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "companies": companies,
        "failures": failures,
    }
    output = arguments.output if arguments.output.is_absolute() else repo_root / arguments.output
    write_payload(output.resolve(), payload)
    print(f"Wrote {output.resolve()} ({len(companies)} companies, {len(failures)} failures)")
    return 0 if companies or not selected else 1


if __name__ == "__main__":
    raise SystemExit(main())
