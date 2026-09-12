#!/usr/bin/env python3
"""Validate and resolve Git-authoritative financial fact packages."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RELATIVE_PATH = Path("data/investment-dashboard/financial_facts.json")
SCHEMA_VERSION = 1
SUPPORTED_METRICS = frozenset({
    "gross_margin", "operating_cash_flow", "revenue_yoy", "net_profit_yoy",
})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def empty_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "authority": "git",
        "supported_metrics": sorted(SUPPORTED_METRICS),
        "facts": [],
    }


def load(path: Path, *, strict: bool = True) -> dict[str, Any]:
    if not path.is_file():
        return empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        if strict:
            raise ValueError(f"invalid financial facts: {path}: {error}") from error
        return empty_payload()
    errors = validate_payload(payload)
    if errors and strict:
        raise ValueError("invalid financial facts: " + "; ".join(errors))
    return payload


def _date(value: Any) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def validate_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    if payload.get("authority") != "git":
        errors.append("authority must be git")
    facts = payload.get("facts")
    if not isinstance(facts, list):
        return errors + ["facts must be a list"]
    identities: set[tuple[str, str, str, str]] = set()
    for index, fact in enumerate(facts):
        prefix = f"facts[{index}]"
        if not isinstance(fact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        ticker = str(fact.get("ticker") or "").upper()
        metric = str(fact.get("metric") or "")
        period = str(fact.get("period") or "")
        unit = str(fact.get("unit") or "")
        if not ticker:
            errors.append(f"{prefix}.ticker")
        if metric not in SUPPORTED_METRICS:
            errors.append(f"{prefix}.metric")
        if not period:
            errors.append(f"{prefix}.period")
        if not unit:
            errors.append(f"{prefix}.unit")
        try:
            numeric_value = float(str(fact.get("actual_value")))
            if not math.isfinite(numeric_value):
                raise ValueError("non-finite")
        except (TypeError, ValueError):
            errors.append(f"{prefix}.actual_value")
        for field in ("evidence_date", "checked_at", "valid_until"):
            if not _date(fact.get(field)):
                errors.append(f"{prefix}.{field}")
        for field in ("evidence_source", "source_identity"):
            if not str(fact.get(field) or "").strip():
                errors.append(f"{prefix}.{field}")
        if not SHA256_RE.fullmatch(str(fact.get("content_sha256") or "")):
            errors.append(f"{prefix}.content_sha256")
        baseline = fact.get("baseline_report_sha256")
        if baseline is not None and not SHA256_RE.fullmatch(str(baseline)):
            errors.append(f"{prefix}.baseline_report_sha256")
        identity = (ticker, metric, period, unit)
        if identity in identities:
            errors.append(f"{prefix} duplicate identity")
        identities.add(identity)
    return errors


def for_ticker(payload: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    normalized = ticker.upper()
    return [
        fact for fact in payload.get("facts", [])
        if isinstance(fact, dict) and str(fact.get("ticker") or "").upper() == normalized
    ]


def resolve(
    facts: list[dict[str, Any]],
    rule: dict[str, Any],
    *,
    baseline_report_sha256: str | None,
) -> dict[str, Any] | None:
    required = ("metric", "operator", "threshold", "period", "unit")
    if any(rule.get(field) in (None, "") for field in required):
        return None
    matches = [
        fact for fact in facts
        if fact.get("metric") == rule.get("metric")
        and str(fact.get("period")) == str(rule.get("period"))
        and fact.get("unit") == rule.get("unit")
        and (
            not fact.get("baseline_report_sha256")
            or fact.get("baseline_report_sha256") == baseline_report_sha256
        )
    ]
    if not matches:
        return {"resolution_status": "missing"}
    identities = {
        (str(item.get("actual_value")), item.get("content_sha256")) for item in matches
    }
    if len(identities) > 1:
        return {"resolution_status": "conflict", "candidates": matches}
    return {"resolution_status": "ready", **matches[0]}


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
    upsert.add_argument("--fact", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    path = root / RELATIVE_PATH
    payload = load(path)
    if arguments.command == "validate":
        print("financial facts=PASS")
        return 0
    fact_path = arguments.fact if arguments.fact.is_absolute() else root / arguments.fact
    fact = json.loads(fact_path.read_text(encoding="utf-8"))
    identity = tuple(str(fact.get(field) or "") for field in ("ticker", "metric", "period", "unit"))
    payload["facts"] = [
        item for item in payload.get("facts", [])
        if tuple(str(item.get(field) or "") for field in ("ticker", "metric", "period", "unit")) != identity
    ] + [fact]
    payload["facts"].sort(key=lambda item: tuple(str(item.get(field) or "") for field in ("ticker", "metric", "period", "unit")))
    errors = validate_payload(payload)
    if errors:
        raise ValueError("invalid financial fact: " + "; ".join(errors))
    save(path, payload)
    print("Saved financial fact: " + ":".join(identity))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
