#!/usr/bin/env python3
"""Generate fail-closed dual-model report judgments for the selected A-share board."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from report_judgment import (
    LLMConfig,
    ROOT,
    build_artifact,
    combine_model_judgments,
    derive_price_bounds,
    failed_artifact,
    load_env_file,
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--board",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "decision_board.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "report_judgments",
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--tickers", help="Comma-separated tickers to process.")
    parser.add_argument(
        "--retry-nonready",
        action="store_true",
        help="Keep current ready artifacts and process only missing, review, error, or stale entries.",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Keep ready and review artifacts; process only missing, error, or stale entries.",
    )
    parser.add_argument(
        "--reconcile-existing",
        action="store_true",
        help="Reapply the current consensus policy to stored two-model results without API calls.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    load_env_file(ROOT / ".env.sentiment")
    load_env_file(ROOT / ".env.sentiment-review")
    primary = LLMConfig.from_environment("SENTIMENT_LLM_")
    review = LLMConfig.from_environment("SENTIMENT_REVIEW_")
    if primary is None or review is None:
        raise RuntimeError("both primary and review model configurations are required")
    board = json.loads(args.board.read_text(encoding="utf-8"))
    decisions = [
        item
        for item in board.get("decisions", [])
        if item.get("market") == "A股" and item.get("ticker") and item.get("report_path")
    ]
    if args.tickers:
        requested = {value.strip().upper() for value in args.tickers.split(",") if value.strip()}
        decisions = [item for item in decisions if str(item.get("ticker") or "").upper() in requested]
    if args.limit:
        decisions = decisions[: args.limit]
    if args.reconcile_existing:
        counts = {"ready": 0, "review": 0, "unchanged": 0}
        for item in decisions:
            output = args.output_dir / f"{item['ticker']}.json"
            try:
                artifact = json.loads(output.read_text(encoding="utf-8"))
                primary_result = artifact["models"]["primary"]["result"]
                review_result = artifact["models"]["review"]["result"]
            except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
                counts["unchanged"] += 1
                continue
            report = ROOT / item["report_path"]
            if (
                artifact.get("report_path") != item["report_path"]
                or not report.is_file()
                or artifact.get("report_sha256") != hashlib.sha256(report.read_bytes()).hexdigest()
            ):
                counts["unchanged"] += 1
                continue
            ready, agreements, judgment = combine_model_judgments(
                primary_result,
                review_result,
                derive_price_bounds(report.read_text(encoding="utf-8").splitlines(), str(item["ticker"])),
            )
            artifact["status"] = "ready" if ready else "review"
            artifact["judgment"] = judgment
            artifact["consensus"] = agreements
            write_json(output, artifact)
            counts[artifact["status"]] += 1
        print(json.dumps({"reconciled": counts}, ensure_ascii=False))
        return 0
    skipped = 0
    if args.retry_nonready or args.retry_errors:
        pending: list[dict[str, Any]] = []
        for item in decisions:
            report = ROOT / item["report_path"]
            output = args.output_dir / f"{item['ticker']}.json"
            try:
                artifact = json.loads(output.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                pending.append(item)
                continue
            reusable_statuses = {"ready", "review"} if args.retry_errors else {"ready"}
            current_ready = (
                artifact.get("status") in reusable_statuses
                and artifact.get("report_path") == item["report_path"]
                and report.is_file()
                and artifact.get("report_sha256")
                == hashlib.sha256(report.read_bytes()).hexdigest()
            )
            if current_ready:
                skipped += 1
            else:
                pending.append(item)
        decisions = pending
    workers = min(6, max(1, args.workers))

    def run(item: dict[str, Any]) -> tuple[str, str, str]:
        report = ROOT / item["report_path"]
        try:
            artifact = build_artifact(
                report, str(item["company"]), str(item["ticker"]), primary, review
            )
        except Exception as exc:  # noqa: BLE001 - every stock gets a fail-closed artifact
            artifact = failed_artifact(
                report,
                str(item["company"]),
                str(item["ticker"]),
                primary.model,
                review.model,
                exc,
            )
        output = args.output_dir / f"{item['ticker']}.json"
        write_json(output, artifact)
        return str(item["ticker"]), str(item["company"]), str(artifact["status"])

    counts = {"ready": 0, "review": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run, item): item for item in decisions}
        for completed, future in enumerate(as_completed(futures), start=1):
            ticker, company, status = future.result()
            counts[status] = counts.get(status, 0) + 1
            print(
                json.dumps(
                    {"completed": completed, "total": len(decisions), "ticker": ticker, "company": company, "status": status},
                    ensure_ascii=False,
                ),
                flush=True,
            )
    print(
        json.dumps(
            {"processed": len(decisions), "skipped_ready": skipped, "counts": counts},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
