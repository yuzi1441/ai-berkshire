#!/usr/bin/env python3
"""Validate and atomically persist Git-authoritative WATCH light signals.

This state is deliberately separate from formal Thesis Drift.  It is written
locally, reviewed through Git, and only read by the dashboard builder.  It
never changes lifecycle, Decision Rules, Checklist state, or holdings.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RELATIVE_PATH = Path("data/investment-dashboard/light_thesis_signals.json")
STATE_RELATIVE_PATH = Path("data/investment-dashboard/company_state.json")
SIGNALS = {"improved", "unchanged", "weakened", "insufficient_evidence"}
PROJECTION_STATUSES = {"current", "stale", "not_applicable", "missing"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _read(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        if default is not None:
            return default
        raise ValueError(f"missing JSON file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def empty_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "authority": "git",
        "scope": "watch_light_thesis_only",
        "updated_at": None,
        "companies": {},
    }


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ticker = _text(record.get("ticker")).upper()
    if not ticker:
        errors.append("ticker is required")
    if record.get("lifecycle_at_review") != "WATCH":
        errors.append(f"{ticker or 'record'} lifecycle_at_review must be WATCH")
    if not _text(record.get("baseline_report_path")):
        errors.append(f"{ticker or 'record'} baseline_report_path is required")
    report_hash = _text(record.get("baseline_report_sha256")).lower()
    if not SHA256_RE.fullmatch(report_hash):
        errors.append(f"{ticker or 'record'} invalid baseline_report_sha256")
    evidence_fingerprint = _text(record.get("evidence_fingerprint")).lower()
    if not SHA256_RE.fullmatch(evidence_fingerprint):
        errors.append(f"{ticker or 'record'} invalid evidence_fingerprint")
    try:
        datetime.fromisoformat(_text(record.get("checked_at")).replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{ticker or 'record'} invalid checked_at")
    if record.get("signal") not in SIGNALS:
        errors.append(f"{ticker or 'record'} invalid signal")
    for field in ("summary", "model", "provider", "provenance"):
        if not _text(record.get(field)):
            errors.append(f"{ticker or 'record'} {field} is required")
    evidence = record.get("material_evidence")
    if not isinstance(evidence, list):
        errors.append(f"{ticker or 'record'} material_evidence must be a list")
    elif any(
        not isinstance(item, dict)
        or not _text(item.get("summary"))
        or not _text(item.get("source"))
        for item in evidence
    ):
        errors.append(f"{ticker or 'record'} invalid material_evidence item")
    return errors


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid schema_version")
    if payload.get("authority") != "git":
        errors.append("authority must be git")
    if payload.get("scope") != "watch_light_thesis_only":
        errors.append("scope must be watch_light_thesis_only")
    companies = payload.get("companies")
    if not isinstance(companies, dict):
        return [*errors, "companies must be an object"]
    for ticker, record in companies.items():
        if not isinstance(record, dict):
            errors.append(f"{ticker} record must be an object")
            continue
        if _text(record.get("ticker")).upper() != str(ticker).upper():
            errors.append(f"{ticker} key/ticker mismatch")
        errors.extend(validate_record(record))
    return errors


def load(path: Path, *, strict: bool = True) -> dict[str, Any]:
    payload = _read(path, empty_payload())
    errors = validate_payload(payload)
    if strict and errors:
        raise ValueError("invalid light thesis signals: " + "; ".join(errors))
    return payload


def project_record(
    record: dict[str, Any] | None,
    *,
    lifecycle: str,
    canonical_report_path: str | None,
    canonical_report_sha256: str | None,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"status": "missing", "signal": None, "reason": "no_light_thesis_signal"}
    projected = dict(record)
    if lifecycle != "WATCH" or record.get("lifecycle_at_review") != "WATCH":
        status, reason = "not_applicable", "current_lifecycle_is_not_watch"
    elif (
        record.get("baseline_report_sha256") != canonical_report_sha256
        or record.get("baseline_report_path") != canonical_report_path
    ):
        status, reason = "stale", "main_report_baseline_changed"
    else:
        status, reason = "current", "watch_baseline_matches"
    projected.update({"status": status, "reason": reason})
    return projected


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _lock_path(repo_root: Path) -> Path:
    digest = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"ai-berkshire-light-thesis-{digest}.lock"


def _current_company(repo_root: Path, ticker: str) -> dict[str, Any]:
    state = _read(repo_root / STATE_RELATIVE_PATH)
    companies = state.get("companies")
    if not isinstance(companies, list):
        raise ValueError("invalid company_state companies")
    matches = [
        item for item in companies
        if isinstance(item, dict) and _text(item.get("ticker")).upper() == ticker
    ]
    if len(matches) != 1:
        raise ValueError(f"ticker must resolve to one current company: {ticker}")
    return matches[0]


def upsert(repo_root: Path, record: dict[str, Any]) -> str:
    """Upsert one WATCH record under a process lock; return changed/noop."""
    repo_root = repo_root.resolve()
    record = dict(record)
    record["ticker"] = _text(record.get("ticker")).upper()
    errors = validate_record(record)
    if errors:
        raise ValueError("invalid light thesis record: " + "; ".join(errors))
    source_path = repo_root / RELATIVE_PATH
    lock_path = _lock_path(repo_root)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        current = _current_company(repo_root, record["ticker"])
        if current.get("lifecycle") != "WATCH":
            raise ValueError(f"light thesis signals only accept current WATCH: {record['ticker']}")
        if record.get("baseline_report_path") != current.get("canonical_report"):
            raise ValueError(f"baseline report path is not current: {record['ticker']}")
        if record.get("baseline_report_sha256") != current.get("canonical_report_sha256"):
            raise ValueError(f"baseline report hash is not current: {record['ticker']}")
        payload = load(source_path, strict=True)
        companies = dict(payload.get("companies") or {})
        previous = companies.get(record["ticker"])
        identity = (
            record["ticker"], record["baseline_report_sha256"], record["evidence_fingerprint"]
        )
        if isinstance(previous, dict):
            previous_identity = (
                previous.get("ticker"), previous.get("baseline_report_sha256"),
                previous.get("evidence_fingerprint"),
            )
            if previous_identity == identity:
                if previous.get("signal") != record.get("signal"):
                    raise ValueError(f"conflicting signal for identical evidence: {record['ticker']}")
                return "noop"
        companies[record["ticker"]] = record
        payload["companies"] = dict(sorted(companies.items()))
        payload["updated_at"] = record["checked_at"]
        errors = validate_payload(payload)
        if errors:
            raise ValueError("invalid light thesis signals: " + "; ".join(errors))
        _write_atomic(source_path, payload)
        return "changed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    upsert_parser = subparsers.add_parser("upsert")
    upsert_parser.add_argument("--input", type=Path, required=True)
    arguments = parser.parse_args()
    source_path = arguments.repo_root.resolve() / RELATIVE_PATH
    if arguments.command == "validate":
        load(source_path, strict=True)
        print("light thesis signals valid")
        return 0
    record = _read(arguments.input)
    print(upsert(arguments.repo_root, record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
