#!/usr/bin/env python3
"""Manual OpenCode runner for daily and deep main-report evidence reviews.

This command never changes human-locked rules.  It invokes the read-only
OpenCode agent, validates the returned JSON with ``main_report_review``, and
atomically replaces one stock/layer result at a time.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from main_report_review import (
    DAILY_REVIEW_DUE_DAYS,
    DEEP_REVIEW_DUE_DAYS,
    aggregate_review_status,
    atomic_write_json,
    codex_layer_run,
    collect_local_evidence,
    collect_official_evidence,
    load_json,
    load_rule_packages,
    model_review_comparison_snapshot,
    now_iso,
    packet_layer_run,
    public_review_snapshot,
    read_price_context,
    result_payload,
    review_due_at,
    review_rules_with_model,
)


DAILY_MODEL = "opencode-go/deepseek-v4-flash"


def parse_iso(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def is_due(run: dict[str, Any] | None) -> bool:
    if not isinstance(run, dict):
        return True
    due = parse_iso(run.get("due_at"))
    return due is None or due <= datetime.now().astimezone()


def json_candidates(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for nested in value.values():
            found.extend(json_candidates(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(json_candidates(nested))
    elif isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                found.extend(json_candidates(json.loads(text)))
            except json.JSONDecodeError:
                pass
    return found


def parse_opencode_json(stdout: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            candidates.extend(json_candidates(json.loads(line)))
        except json.JSONDecodeError:
            continue
    for candidate in reversed(candidates):
        if any(key in candidate for key in ("rule_results", "task_results", "results", "rules")):
            return candidate
    raise RuntimeError("OpenCode did not emit a review JSON object")


def invoke_opencode(
    *,
    repo_root: Path,
    agent: str,
    model: str,
    variant: str,
    system: str,
    user: str,
    timeout_seconds: int,
    opencode_bin: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    prompt = f"{system}\n\n任务输入：{user}\n\n只输出符合任务 schema 的 JSON 对象。"
    command = [
        opencode_bin,
        "run",
        "--pure",
        "--agent", agent,
        "--model", model,
        "--variant", variant,
        "--format", "json",
        "--dir", str(repo_root),
        prompt,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "OpenCode failed").strip()
        raise RuntimeError(detail[-1200:])
    return parse_opencode_json(completed.stdout), {
        "requested": f"OpenCode --model {model} --variant {variant}",
        "effective": f"OpenCode --model {model} --variant {variant}",
    }


def layer_payload(
    *,
    layer: str,
    model: str,
    variant: str,
    package: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    review = result.get("model_review") or {}
    summary = result.get("summary") or {}
    generated_at = result.get("generated_at") or now_iso()
    return {
        "schema_version": 1,
        "layer": layer,
        "run_id": f"{layer}-{package.get('ticker')}-{generated_at}",
        "ticker": package.get("ticker"),
        "company": package.get("company"),
        "reviewer": model,
        "model": model,
        "variant": variant,
        "generated_at": generated_at,
        "rules_fingerprint": package.get("rules_fingerprint"),
        "evidence_fingerprint": result.get("evidence_fingerprint"),
        "run_status": review.get("status") or summary.get("status") or "error",
        "status": summary.get("status") or "data_gap",
        "label": summary.get("label") or "复核完成",
        "evidence_state": "current" if result.get("current_evidence_count") else "historical_or_insufficient",
        "current_evidence_count": result.get("current_evidence_count") or 0,
        "latest_evidence_date": result.get("latest_evidence_date"),
        "tasks": review.get("rules") or [],
        "summary": summary,
        "evidence_documents": result.get("evidence_documents") or [],
        "source": "本地资料优先；不足时由 OpenCode 搜索并核对官方披露。",
        "due_at": review_due_at(generated_at, DAILY_REVIEW_DUE_DAYS if layer == "daily" else DEEP_REVIEW_DUE_DAYS),
    }


def publish_snapshot(repo_root: Path, rules_dir: Path, legacy_dir: Path, layers_dir: Path) -> None:
    snapshot = public_review_snapshot(rules_dir, repo_root / "local" / "fundamental-review-current", legacy_dir=legacy_dir, layers_dir=layers_dir)
    public_paths = (
        repo_root / "data" / "investment-dashboard" / "main_report_review.json",
        repo_root / "site" / "data" / "main_report_review.json",
    )
    for path in public_paths:
        atomic_write_json(path, snapshot)
        # The runner is invoked as root on the VPS, while dashboard_server runs
        # as an unprivileged account.  These are explicitly public dashboard
        # snapshots, so keep their final atomic replacement world-readable.
        path.chmod(0o644)


def seed_legacy(repo_root: Path, rules_dir: Path, layers_dir: Path) -> int:
    comparison = model_review_comparison_snapshot(repo_root)
    by_ticker = {str(row.get("ticker")): row for row in comparison.get("reviews") or [] if isinstance(row, dict)}
    codex = load_json(rules_dir.parent / "codex_direct_manual_review.json", {})
    codex_by_ticker = {str(row.get("ticker")): row for row in codex.get("reviews") or [] if isinstance(row, dict)}
    count = 0
    for package in load_rule_packages(rules_dir):
        ticker = str(package.get("ticker"))
        model_packet = by_ticker.get(ticker) or {}
        daily = packet_layer_run(model_packet.get("deepseek"), layer="daily", default_reviewer="DeepSeek", rules_fingerprint=package.get("rules_fingerprint"), migrated_seed=True)
        deep = codex_layer_run(codex_by_ticker.get(ticker), rules_fingerprint=package.get("rules_fingerprint"))
        for layer, payload in (("daily", daily), ("deep", deep)):
            if payload:
                path = layers_dir / layer / f"{ticker}.json"
                if not path.exists():
                    atomic_write_json(path, payload)
                    count += 1
    return count


def due_queue(repo_root: Path, rules_dir: Path, legacy_dir: Path, layers_dir: Path) -> list[dict[str, Any]]:
    snapshot = public_review_snapshot(
        rules_dir,
        repo_root / "local" / "fundamental-review-current",
        legacy_dir=legacy_dir,
        layers_dir=layers_dir,
    )
    rows = []
    for review in snapshot.get("reviews") or []:
        if review.get("rule_state") != "active":
            rows.append({"ticker": review.get("ticker"), "company": review.get("company"), "layer": "rules", "status": "stale_rules"})
            continue
        for layer in ("daily", "deep"):
            current = ((review.get(layer) or {}).get("current"))
            if is_due(current):
                rows.append({
                    "ticker": review.get("ticker"),
                    "company": review.get("company"),
                    "layer": layer,
                    "status": (current or {}).get("status") or "not_run",
                    "due_at": (review.get(layer) or {}).get("due_at"),
                })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--rules-dir", type=Path, default=Path("data/investment-dashboard/main-report-review-rules"))
    parser.add_argument("--legacy-dir", type=Path, default=Path("local/fundamental-review-full"))
    parser.add_argument("--layers-dir", type=Path, default=Path("local/fundamental-review-layers"))
    parser.add_argument("--layer", choices=("daily", "deep"))
    parser.add_argument("--ticker", action="append", default=[])
    parser.add_argument("--all-due", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--variant", default="max")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--opencode-bin", default="opencode")
    parser.add_argument("--seed-legacy", action="store_true")
    parser.add_argument("--queue", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    rules_dir = args.rules_dir if args.rules_dir.is_absolute() else root / args.rules_dir
    legacy_dir = args.legacy_dir if args.legacy_dir.is_absolute() else root / args.legacy_dir
    layers_dir = args.layers_dir if args.layers_dir.is_absolute() else root / args.layers_dir
    if args.seed_legacy:
        count = seed_legacy(root, rules_dir, layers_dir)
        if args.publish:
            publish_snapshot(root, rules_dir, legacy_dir, layers_dir)
        if not args.queue:
            print(json.dumps({"seeded": count}, ensure_ascii=False))
            return 0
    if args.queue:
        print(json.dumps({"queue": due_queue(root, rules_dir, legacy_dir, layers_dir)}, ensure_ascii=False, indent=2))
        return 0
    if not args.layer:
        parser.error("--layer is required unless --seed-legacy is used")
    if not args.ticker and not args.all_due:
        parser.error("provide --ticker or --all-due")
    model = args.model or (DAILY_MODEL if args.layer == "daily" else None)
    if args.layer == "daily" and model != DAILY_MODEL:
        parser.error(f"daily layer is fixed to {DAILY_MODEL}")
    if not model:
        parser.error("deep layer requires --model provider/model")
    wanted = {value.upper() for value in args.ticker}
    outcomes: list[dict[str, str]] = []
    for package in load_rule_packages(rules_dir):
        ticker = str(package.get("ticker"))
        path = layers_dir / args.layer / f"{ticker}.json"
        if wanted and ticker not in wanted:
            continue
        if not wanted and args.all_due and not is_due(load_json(path, {})):
            continue
        if package.get("rule_state") != "active":
            outcomes.append({"ticker": ticker, "status": "stale_rules"})
            continue
        documents = collect_local_evidence(root, package)
        if not any(doc.get("source_role") in {"local_current_evidence", "zcode_current_evidence_extract"} for doc in documents):
            documents.extend(collect_official_evidence(package))
        price_context = read_price_context(root, ticker)
        try:
            model_review = review_rules_with_model(
                package,
                documents,
                price_context=price_context,
                responder=lambda system, user: invoke_opencode(
                    repo_root=root, agent="fundamental-review-daily" if args.layer == "daily" else "fundamental-review-deep",
                    model=model, variant=args.variant, system=system, user=user,
                    timeout_seconds=args.timeout, opencode_bin=args.opencode_bin,
                ),
                reviewer_model=model,
            )
            payload = result_payload(package, documents, model_review, price_context=price_context)
            atomic_write_json(path, layer_payload(layer=args.layer, model=model, variant=args.variant, package=package, result=payload))
            outcomes.append({"ticker": ticker, "status": payload["summary"]["status"]})
        except Exception as error:  # preserve last good current result
            outcomes.append({"ticker": ticker, "status": "error", "message": str(error)[:240]})
        if args.publish:
            publish_snapshot(root, rules_dir, legacy_dir, layers_dir)
    print(json.dumps({"layer": args.layer, "model": model, "outcomes": outcomes}, ensure_ascii=False, indent=2))
    return 1 if any(row["status"] == "error" for row in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
