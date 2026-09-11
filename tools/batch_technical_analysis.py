#!/usr/bin/env python3
"""Generate technical-analysis reports for dashboard companies in one local run."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import technical_analysis as technical  # noqa: E402


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from error


def load_decisions(repo_root: Path, market: str | list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    board_path = repo_root / "data" / "investment-dashboard" / "decision_board.json"
    with board_path.open(encoding="utf-8") as handle:
        board = json.load(handle)
    decisions = board.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError(f"invalid dashboard decisions in {board_path}")
    markets = {market} if isinstance(market, str) else set(market)
    selected = [
        item
        for item in decisions
        if isinstance(item, dict)
        and item.get("market") in markets
        and item.get("company")
        and item.get("ticker")
        and item.get("report_path")
    ]
    return sorted(selected, key=lambda item: (str(item["company"]), str(item["ticker"])))


def load_exclusions(repo_root: Path) -> dict[str, str]:
    path = (
        repo_root
        / "data"
        / "investment-dashboard"
        / "technical_analysis_exclusions.json"
    )
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != 1 or not isinstance(payload.get("companies"), dict):
        raise ValueError(f"invalid technical-analysis exclusions in {path}")
    return {
        str(company): str(reason)
        for company, reason in payload["companies"].items()
        if company and reason
    }


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[/\\:*?"<>|\x00-\x1f]+', "-", value).strip(" .-")
    return cleaned or "company"


def report_destination(
    decision: dict[str, Any], repo_root: Path, analysis_date: date
) -> tuple[Path, Path]:
    base_report = (repo_root / str(decision["report_path"])).resolve()
    reports_root = (repo_root / "reports").resolve()
    if reports_root not in base_report.parents or not base_report.is_file():
        raise ValueError(f"invalid base report: {decision.get('report_path')}")
    filename = (
        f"{safe_filename(str(decision['company']))}-technical-analysis-"
        f"{analysis_date.strftime('%Y%m%d')}.md"
    )
    return base_report, base_report.parent / filename


def fetch_history_with_retry(
    symbol: str, start: date, end: date, attempts: int
) -> tuple[list[technical.PriceRow], dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return technical.fetch_yahoo_history(symbol, start, end)
        except technical.TechnicalAnalysisError as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def generate_one(
    decision: dict[str, Any],
    *,
    repo_root: Path,
    as_of: date,
    attempts: int,
    force: bool,
    write_report: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    company = str(decision["company"])
    ticker, yahoo_symbol, market = technical.normalize_ticker(
        str(decision["ticker"]), str(decision["market"])
    )
    base_report, destination = report_destination(decision, repo_root, date.today())
    base_cutoff, base_report_date = technical.report_context_dates(base_report)
    related_files = technical.referenced_project_files(base_report, repo_root)
    fundamental_bands = technical.fundamental_entry_bands(base_report, market)

    rows, source = fetch_history_with_retry(
        yahoo_symbol,
        as_of - timedelta(days=900),
        as_of,
        attempts,
    )
    rows = technical.remove_incomplete_daily_bar(rows, source, market)
    rows = [row for row in rows if row.trading_date <= as_of]
    if not rows:
        raise technical.TechnicalAnalysisError("no valid rows remain at the requested cutoff")
    result = technical.compute_analysis(
        rows,
        company=company,
        ticker=ticker,
        yahoo_symbol=yahoo_symbol,
        market=market,
        as_of=as_of,
        source=source,
    )
    result["analysis_mode"] = "daily_close"
    if write_report:
        content = technical.render_markdown(
            result,
            base_report=base_report.relative_to(repo_root).as_posix(),
            base_report_cutoff=base_cutoff.isoformat() if base_cutoff else decision.get("data_cutoff"),
            base_report_date=base_report_date.isoformat() if base_report_date else None,
            related_files=related_files,
            fundamental_bands=fundamental_bands,
        )
        technical.write_output(destination, content, force=force)
    quality = result["data_quality"]
    guidance = technical.decision_snapshot(result, fundamental_bands)
    return {
        "company": company,
        "ticker": ticker,
        "status": "generated" if write_report else "ready",
        "report_path": destination.relative_to(repo_root).as_posix() if write_report else None,
        "base_report": base_report.relative_to(repo_root).as_posix(),
        "base_report_cutoff": base_cutoff.isoformat() if base_cutoff else decision.get("data_cutoff"),
        "related_file_count": len(related_files),
        "requested_cutoff": result["requested_cutoff"],
        "data_cutoff": result["data_cutoff"],
        "technical_state": result["technical_state"],
        "state": result["technical_state"],
        "market": market,
        "latest_price": result["latest"]["close"],
        "observation_zone": technical.display_zone(guidance["technical_zone"]),
        "combined_candidate_zone": technical.display_intersections(guidance["intersections"], result["latest"].get("currency") or ""),
        "valid_buy_candidate": guidance["answer"],
        "lights": guidance["lights"],
        "analysis": result,
        "publishable": bool(quality["publishable"]),
        "confidence": quality["confidence"],
        "cross_check": result["cross_check"].get("status"),
        "warnings": quality["warnings"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def carry_forward(payload: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    """Keep actual success dates; failures never become fresh successful rows."""
    if previous and previous.get("schema_version") != 1:
        raise ValueError("unsupported previous technical snapshot schema")
    previous_rows = {row["ticker"]: row for row in previous.get("companies", []) if isinstance(row, dict) and row.get("ticker")}
    rows = dict(previous_rows)
    attempted_at = payload["generated_at"]
    for item in payload["results"]:
        rows[item["ticker"]] = dict(item, last_attempt_at=attempted_at, last_success_at=attempted_at)
    for failure in payload["failures"]:
        ticker = failure["ticker"]
        previous_row = previous_rows.get(ticker, {})
        rows[ticker] = dict(previous_row, ticker=ticker, company=failure["company"],
                            status="stale" if previous_row else failure["status"],
                            freshness="stale" if previous_row else "unknown",
                            last_attempt_at=attempted_at, last_error=failure["error"],
                            attempt_status=failure["status"])
    payload["companies"] = [rows[ticker] for ticker in sorted(rows)]
    payload["status"] = "partial" if payload["failures"] and payload["results"] else "failed" if payload["failures"] else "ok"
    payload["last_success_at"] = attempted_at if payload["results"] else previous.get("last_success_at")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    market_group = parser.add_mutually_exclusive_group()
    market_group.add_argument("--market", help="one market; kept for scheduler compatibility")
    market_group.add_argument(
        "--markets",
        nargs="+",
        choices=("A股", "港股", "美股"),
        help="one or more markets sharing one structured latest output",
    )
    parser.add_argument("--as-of", type=parse_iso_date, default=date.today())
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--write-reports",
        action="store_true",
        help="opt in to writing a dated Markdown report; default is structured latest state",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "technical_daily_snapshot.json",
        help="structured daily output path",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--manifest", type=Path)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    if arguments.attempts < 1:
        print("error: --attempts must be at least 1", file=sys.stderr)
        return 2
    requested_markets = arguments.markets or [arguments.market or "A股"]
    all_decisions = load_decisions(repo_root, requested_markets)
    exclusion_reasons = load_exclusions(repo_root)
    excluded = [
        {
            "company": str(item["company"]),
            "ticker": str(item["ticker"]),
            "reason": exclusion_reasons[str(item["company"])],
        }
        for item in all_decisions
        if str(item["company"]) in exclusion_reasons
    ]
    decisions = [
        item
        for item in all_decisions
        if str(item["company"]) not in exclusion_reasons
    ]
    if arguments.limit is not None:
        decisions = decisions[: max(arguments.limit, 0)]
    manifest_path = arguments.manifest or (
        repo_root
        / "logs"
        / f"technical-analysis-batch-{arguments.as_of.strftime('%Y%m%d')}.json"
    )

    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions, start=1):
        company = str(decision["company"])
        ticker = str(decision["ticker"])
        try:
            result = generate_one(
                decision,
                repo_root=repo_root,
                as_of=arguments.as_of,
                attempts=arguments.attempts,
                force=arguments.force,
                write_report=arguments.write_reports,
            )
            results.append(result)
            marker = "可发布" if result["publishable"] else "待复核"
            print(
                f"[{index}/{len(decisions)}] {company} {ticker}: "
                f"{marker}, 技术日 {result['data_cutoff']}, {result['elapsed_seconds']}s"
            )
        except (OSError, ValueError, json.JSONDecodeError, technical.TechnicalAnalysisError) as error:
            failure = {
                "company": company,
                "ticker": ticker,
                "status": "insufficient_history" if "valid trading rows are required" in str(error) else "failed",
                "error": str(error),
            }
            failures.append(failure)
            print(f"[{index}/{len(decisions)}] {company} {ticker}: FAILED {error}", file=sys.stderr)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "market": requested_markets[0] if len(requested_markets) == 1 else "+".join(requested_markets),
        "markets": requested_markets,
        "requested_cutoff": arguments.as_of.isoformat(),
        "source_decision_count": len(all_decisions),
        "selected_count": len(decisions),
        "excluded_count": len(excluded),
        "generated_count": len(results),
        "publishable_count": sum(bool(item["publishable"]) for item in results),
        "review_count": sum(not bool(item["publishable"]) for item in results),
        "failed_count": len(failures),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "results": results,
        "excluded": excluded,
        "failures": failures,
    }
    if not arguments.write_reports:
        payload["output_mode"] = "structured_latest"
        output = arguments.output if arguments.output.is_absolute() else repo_root / arguments.output
        previous = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
        payload = carry_forward(payload, previous)
        write_manifest(output, payload)
    write_manifest(manifest_path, payload)
    print(
        f"Completed {len(results)}/{len(decisions)} reports; "
        f"{len(failures)} failed. Manifest: {manifest_path}"
    )
    # Per-company failures are explicit in the snapshot. Publish successful
    # rows and continue the scheduler's quotes/build phases on partial success.
    return 1 if failures and not results and any(item["status"] == "failed" for item in failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
