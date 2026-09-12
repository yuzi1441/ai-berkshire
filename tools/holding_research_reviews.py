#!/usr/bin/env python3
"""Manage Git-authoritative, holding-cycle-bound research review results.

Execution facts (position state, cost and weight) remain in runtime
``post_buy_tracking.json``.  This file stores only publishable research
results and applies them when all immutable bindings still match.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from source_hash import canonical_file_sha256


ROOT = Path(__file__).resolve().parents[1]
RELATIVE_PATH = Path("data/investment-dashboard/holding_research_reviews.json")
SCHEMA_VERSION = 1
THESIS_STATUSES = frozenset({"not_established", "healthy", "borderline", "damaged", "broken"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def empty_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "authority": "git",
        "description": "Publishable holding research only; execution facts remain runtime-authoritative.",
        "reviews": {},
    }


def load(path: Path, *, strict: bool = True) -> dict[str, Any]:
    if not path.is_file():
        return empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        if strict:
            raise ValueError(f"invalid holding research reviews: {path}: {error}") from error
        return empty_payload()
    errors = validate_payload(payload)
    if errors and strict:
        raise ValueError("invalid holding research reviews: " + "; ".join(errors))
    return payload if isinstance(payload, dict) else empty_payload()


def _valid_date(value: Any) -> bool:
    if value in (None, ""):
        return True
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def validate_payload(payload: Any, *, repo_root: Path | None = None) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    if payload.get("authority") != "git":
        errors.append("authority must be git")
    reviews = payload.get("reviews")
    if not isinstance(reviews, dict):
        return errors + ["reviews must be an object"]
    root = repo_root.resolve() if repo_root else None
    for key, review in reviews.items():
        prefix = f"reviews.{key}"
        if not isinstance(review, dict):
            errors.append(f"{prefix} must be an object")
            continue
        ticker = str(review.get("ticker") or "").upper()
        position_id = str(review.get("position_id") or "")
        if key != position_id or not ticker or not position_id.startswith(f"{ticker}:"):
            errors.append(f"{prefix} identity mismatch")
        for field in ("original_buy_thesis_sha256", "report_sha256"):
            if not SHA256_RE.fullmatch(str(review.get(field) or "")):
                errors.append(f"{prefix}.{field}")
        if review.get("thesis_status") not in THESIS_STATUSES:
            errors.append(f"{prefix}.thesis_status")
        score = review.get("health_score")
        if score is not None and (not isinstance(score, (int, float)) or isinstance(score, bool) or not 1 <= score <= 10):
            errors.append(f"{prefix}.health_score")
        for field in ("reviewed_at", "next_review_date"):
            if not _valid_date(review.get(field)):
                errors.append(f"{prefix}.{field}")
        for field in ("metrics", "evidence"):
            if not isinstance(review.get(field, []), list):
                errors.append(f"{prefix}.{field}")
        report_path = str(review.get("report_path") or "")
        if not report_path:
            errors.append(f"{prefix}.report_path")
        elif root is not None:
            candidate = (root / report_path).resolve()
            if root not in candidate.parents or not candidate.is_file():
                errors.append(f"{prefix}.report_path missing")
            elif canonical_file_sha256(candidate) != review.get("report_sha256"):
                errors.append(f"{prefix}.report_sha256 mismatch")
    return errors


def binding_status(
    review: dict[str, Any] | None,
    position: dict[str, Any],
    original_buy_theses: dict[str, Any],
    repo_root: Path,
) -> tuple[str, list[str]]:
    if not isinstance(review, dict):
        return "unreviewed", ["no_git_research_review"]
    reasons: list[str] = []
    ticker = str(position.get("ticker") or "").upper()
    position_id = str(position.get("position_id") or "")
    active_id = str((original_buy_theses.get("active_position_ids") or {}).get(ticker) or "")
    cycle = (original_buy_theses.get("cycles") or {}).get(position_id)
    if review.get("ticker") != ticker:
        reasons.append("ticker_mismatch")
    if review.get("position_id") != position_id:
        reasons.append("position_id_mismatch")
    if active_id != position_id:
        reasons.append("active_position_mismatch")
    if not isinstance(cycle, dict):
        reasons.append("original_buy_thesis_missing")
    elif review.get("original_buy_thesis_sha256") != cycle.get("source_hash"):
        reasons.append("original_buy_thesis_sha256_mismatch")
    raw_path = str(review.get("report_path") or "")
    report = (repo_root.resolve() / raw_path).resolve()
    if repo_root.resolve() not in report.parents or not report.is_file():
        reasons.append("research_report_missing")
    elif canonical_file_sha256(report) != review.get("report_sha256"):
        reasons.append("research_report_sha256_mismatch")
    return ("matched", []) if not reasons else ("binding_mismatch", reasons)


def apply_review(
    projection: dict[str, Any],
    *,
    review: dict[str, Any] | None,
    position: dict[str, Any],
    original_buy_theses: dict[str, Any],
    repo_root: Path,
    allow_legacy: bool = False,
) -> dict[str, Any]:
    status, reasons = binding_status(review, position, original_buy_theses, repo_root)
    projection["research_binding_status"] = status
    projection["research_binding_reasons"] = reasons
    if status == "matched" and review is not None:
        projection.update({
            "thesis_report_path": review.get("report_path"),
            "thesis_status": review.get("thesis_status"),
            "health_score": review.get("health_score"),
            "last_review_date": review.get("reviewed_at"),
            "next_review_date": review.get("next_review_date"),
            "review_action": review.get("review_action"),
            "metrics": review.get("metrics") or [],
            "research_evidence": review.get("evidence") or [],
            "research_provenance": review.get("provenance"),
        })
    elif not allow_legacy:
        projection.update({
            "thesis_status": "not_established",
            "health_score": None,
            "last_review_date": None,
            "next_review_date": None,
            "review_action": None,
            "metrics": [],
            "research_evidence": [],
        })
    else:
        projection["research_binding_status"] = "runtime_legacy"
    return projection


def save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    upsert = subparsers.add_parser("upsert")
    upsert.add_argument("--record", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    path = root / RELATIVE_PATH
    if arguments.command == "validate":
        errors = validate_payload(load(path), repo_root=root)
        if errors:
            print("FAIL: " + "; ".join(errors))
            return 1
        print("holding research reviews=PASS")
        return 0
    record_path = arguments.record if arguments.record.is_absolute() else root / arguments.record
    record = json.loads(record_path.read_text(encoding="utf-8"))
    payload = load(path)
    key = str(record.get("position_id") or "")
    payload.setdefault("reviews", {})[key] = record
    errors = validate_payload(payload, repo_root=root)
    if errors:
        raise ValueError("invalid holding research review: " + "; ".join(errors))
    save(path, payload)
    print(f"Saved holding research review: {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
