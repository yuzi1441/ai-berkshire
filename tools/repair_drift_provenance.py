#!/usr/bin/env python3
"""One-time, semantics-preserving repair of 2026-09-03 Drift evidence paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import drift_provenance


OLD_BATCH_PATH = "reports/thesis-drift-batch/A股-WATCH-全量论文漂移检测-20260903-v2.json"
ARCHIVE_PATH = "research/sources/thesis-drift-batch/2026-09-03-watch-drift-v2.json"
AUDIT_PATH = "research/sources/thesis-drift-batch/2026-09-03-provenance-repair.json"
DRIFT_PATH = "data/investment-dashboard/drift_states.json"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _batch_by_ticker(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("companies")
    if not isinstance(rows, list):
        raise ValueError("batch companies must be a list")
    return {
        str(item.get("ticker") or "").upper(): item
        for item in rows
        if isinstance(item, dict) and item.get("ticker")
    }


def _replacement_evidence_present(item: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(item, dict)
        and item.get("summary")
        and item.get("current_evidence")
        and item.get("facts_sources")
    )


def _semantic_projection(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    for record in (value.get("companies") or {}).values():
        if not isinstance(record, dict):
            continue
        record.pop("facts_sources", None)
        for historical in record.get("review_history", []):
            if isinstance(historical, dict):
                historical.pop("facts_sources", None)
    return value


def repair_payload(
    drift_payload: dict[str, Any], batch_payload: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before_semantics = _semantic_projection(drift_payload)
    repaired = deepcopy(drift_payload)
    batch = _batch_by_ticker(batch_payload)
    mappings: list[dict[str, Any]] = []

    def repair_sources(ticker: str, location: str, record: dict[str, Any]) -> None:
        sources = record.get("facts_sources")
        if not isinstance(sources, list):
            raise ValueError(f"{ticker} {location} facts_sources must be a list")
        updated: list[str] = []
        for raw in sources:
            reason = None
            evidence_present = None
            if raw == OLD_BATCH_PATH:
                reason = "archived_batch_source"
                evidence_present = ticker in batch
            elif isinstance(raw, str) and raw.startswith("/tmp/"):
                reason = "lost_ephemeral_source"
                evidence_present = _replacement_evidence_present(batch.get(ticker))
            if reason:
                if not evidence_present:
                    raise ValueError(
                        f"batch artifact does not preserve evidence for {ticker}: {raw}"
                    )
                mappings.append({
                    "ticker": ticker,
                    "location": location,
                    "old_reference": raw,
                    "replacement_reference": ARCHIVE_PATH,
                    "reason": reason,
                    "replacement_evidence_present": True,
                })
                raw = ARCHIVE_PATH
            if raw not in updated:
                updated.append(raw)
        record["facts_sources"] = updated

    for ticker, record in (repaired.get("companies") or {}).items():
        if not isinstance(record, dict):
            continue
        repair_sources(str(ticker), "current", record)
        for index, historical in enumerate(record.get("review_history", [])):
            if isinstance(historical, dict):
                repair_sources(str(ticker), f"review_history[{index}]", historical)

    if _semantic_projection(repaired) != before_semantics:
        raise ValueError("semantic fields changed during provenance repair")
    return repaired, mappings


def write_atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-batch", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    source = args.source_batch.resolve()
    source_bytes = source.read_bytes()
    batch_payload = json.loads(source_bytes)
    drift_path = root / DRIFT_PATH
    drift_payload = json.loads(drift_path.read_text(encoding="utf-8"))
    repaired, mappings = repair_payload(drift_payload, batch_payload)
    source_hash = sha256_bytes(source_bytes)
    audit = {
        "schema_version": 1,
        "migration_id": "drift-provenance-repair-2026-09-03-v1",
        "migration_date": "2026-09-08",
        "artifact_role": "provenance_repair_audit_only",
        "investment_semantics_changed": False,
        "original_source_identity": OLD_BATCH_PATH,
        "archived_evidence_path": ARCHIVE_PATH,
        "source_sha256": source_hash,
        "archived_sha256": source_hash,
        "repaired_reference_count": len(mappings),
        "affected_tickers": sorted({item["ticker"] for item in mappings}),
        "repairs": mappings,
    }
    print(json.dumps({
        "status": "write_pending" if args.write else "dry_run",
        "repaired_reference_count": len(mappings),
        "affected_ticker_count": len(audit["affected_tickers"]),
        "source_sha256": source_hash,
        "semantic_changes": 0,
    }, ensure_ascii=False, indent=2))
    if not args.write:
        return 0

    archive = root / ARCHIVE_PATH
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists() and archive.read_bytes() != source_bytes:
        raise ValueError(f"archive already exists with different bytes: {archive}")
    if not archive.exists():
        shutil.copyfile(source, archive)
    if sha256_bytes(archive.read_bytes()) != source_hash:
        raise ValueError("archived evidence SHA does not match source SHA")
    errors = drift_provenance.validate_drift_facts_sources(root, repaired)
    if errors:
        raise ValueError("repaired Drift provenance invalid: " + "; ".join(errors))
    write_atomic_json(drift_path, repaired)
    write_atomic_json(root / AUDIT_PATH, audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
