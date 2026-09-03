#!/usr/bin/env python3
"""Reconcile persisted state while assembling a production release.

The release publisher copies a clean Git checkout into a new directory.  A
small subset of JSON files has a mixed authority model: Git contains reviewed
state changes, while the previous release may contain runtime history.  This
module merges only those explicitly defined collections.  It never merges a
previous current record that is absent from the new Git state; an explicit
source removal therefore remains a removal.

This is a release-assembly helper, not a dashboard or Rule Lifecycle fallback.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


STATE_RELATIVE = Path("data/investment-dashboard")
MERGE_FILES = {
    "drift": "drift_states.json",
    "lifecycle": "rule_lifecycle.json",
    "change_log": "rule_change_log.json",
}


def _read(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {label}: expected JSON object: {path}")
    return payload


def _validate(payload: dict[str, Any], kind: str, *, path: Path) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError(f"invalid {kind} schema_version: {path}")
    if kind == "change_log":
        if not isinstance(payload.get("changes"), list) or not isinstance(payload.get("sync_runs"), list):
            raise ValueError(f"invalid rule_change_log collections: {path}")
        return
    if not isinstance(payload.get("companies"), dict):
        raise ValueError(f"invalid {kind} companies collection: {path}")
    if any(not isinstance(key, str) or not isinstance(value, dict) for key, value in payload["companies"].items()):
        raise ValueError(f"invalid {kind} company record: {path}")


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unique_records(*collections: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for collection in collections:
        for item in collection:
            key = _json_key(item)
            if key in seen:
                continue
            seen.add(key)
            result.append(copy.deepcopy(item))
    return result


def _merge_review_history(source: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(source)
    source_history = result.get("review_history")
    previous_history = previous.get("review_history")
    if isinstance(previous_history, list):
        if not isinstance(source_history, list):
            source_history = []
        result["review_history"] = _unique_records(previous_history, source_history)
    return result


def _merge_lifecycle_record(source: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    """Keep source current fields and only carry explicit history fields."""
    result = copy.deepcopy(source)
    for field in ("history", "review_history", "lifecycle_history", "sync_history"):
        if isinstance(previous.get(field), list):
            result[field] = _unique_records(previous[field], result.get(field, []))
    return result


def _merge_payload(source: dict[str, Any], previous: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "change_log":
        result = copy.deepcopy(source)
        result["changes"] = _unique_records(previous["changes"], source["changes"])
        result["sync_runs"] = _unique_records(previous["sync_runs"], source["sync_runs"])
        return result

    result = copy.deepcopy(source)
    companies: dict[str, Any] = {}
    for ticker, record in source["companies"].items():
        previous_record = previous["companies"].get(ticker)
        if isinstance(previous_record, dict):
            if kind == "drift":
                companies[ticker] = _merge_review_history(record, previous_record)
            else:
                companies[ticker] = _merge_lifecycle_record(record, previous_record)
        else:
            companies[ticker] = copy.deepcopy(record)
    # The source company set is authoritative.  Do not append previous-only
    # current records, because doing so would resurrect an intentional removal.
    result["companies"] = companies
    return result


def reconcile_file(previous: Path, source: Path, output: Path, kind: str) -> str:
    """Write the release payload and return the selected authority path."""
    if kind not in MERGE_FILES:
        raise ValueError(f"unsupported release state kind: {kind}")
    previous_exists = previous.is_file()
    source_exists = source.is_file()
    if not source_exists and not previous_exists:
        return "missing"
    if source_exists:
        source_payload = _read(source, label=kind)
        _validate(source_payload, kind, path=source)
    if previous_exists:
        previous_payload = _read(previous, label=f"previous {kind}")
        _validate(previous_payload, kind, path=previous)
    if not source_exists:
        # Preserve the runtime seed byte-for-byte when Git has no state file
        # yet.  Validation above still makes a corrupt previous release fail
        # closed, but a first-deploy compatibility copy does not reformat it.
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(previous.read_bytes())
        temporary.replace(output)
        return "previous"
    if not previous_exists:
        payload = source_payload
        selected = "source"
    else:
        payload = _merge_payload(source_payload, previous_payload, kind)
        selected = "merged"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return selected


def reconcile_release(previous_root: Path, staging_root: Path) -> dict[str, str]:
    previous_data = previous_root / STATE_RELATIVE
    staging_data = staging_root / STATE_RELATIVE
    result: dict[str, str] = {}
    for kind, filename in MERGE_FILES.items():
        result[kind] = reconcile_file(
            previous_data / filename,
            staging_data / filename,
            staging_data / filename,
            kind,
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    args = parser.parse_args()
    previous_root = args.previous_root.resolve()
    staging_root = args.staging_root.resolve()
    result = reconcile_release(previous_root, staging_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
