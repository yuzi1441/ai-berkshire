#!/usr/bin/env python3
"""Generate technical-analysis reports for dashboard companies in one local run."""

from __future__ import annotations

import argparse
import json
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


def load_decisions(repo_root: Path, market: str) -> list[dict[str, Any]]:
    board_path = repo_root / "data" / "investment-dashboard" / "decision_board.json"
    with board_path.open(encoding="utf-8") as handle:
        board = json.load(handle)
    decisions = board.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError(f"invalid dashboard decisions in {board_path}")
    selected = [
        item
        for item in decisions
        if isinstance(item, dict)
        and item.get("market") == market
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
    return {
        "company": company,
        "ticker": ticker,
        "status": "generated",
        "report_path": destination.relative_to(repo_root).as_posix(),
        "base_report": base_report.relative_to(repo_root).as_posix(),
        "base_report_cutoff": base_cutoff.isoformat() if base_cutoff else decision.get("data_cutoff"),
        "related_file_count": len(related_files),
        "requested_cutoff": result["requested_cutoff"],
        "data_cutoff": result["data_cutoff"],
        "technical_state": result["technical_state"],
        "publishable": bool(quality["publishable"]),
        "confidence": quality["confidence"],
        "cross_check": result["cross_check"].get("status"),
        "warnings": quality["warnings"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--market", default="A股")
    parser.add_argument("--as-of", type=parse_iso_date, default=date.today())
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--manifest", type=Path)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    if arguments.attempts < 1:
        print("error: --attempts must be at least 1", file=sys.stderr)
        return 2
    all_decisions = load_decisions(repo_root, arguments.market)
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
                "status": "failed",
                "error": str(error),
            }
            failures.append(failure)
            print(f"[{index}/{len(decisions)}] {company} {ticker}: FAILED {error}", file=sys.stderr)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "market": arguments.market,
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
    write_manifest(manifest_path, payload)
    print(
        f"Completed {len(results)}/{len(decisions)} reports; "
        f"{len(failures)} failed. Manifest: {manifest_path}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
