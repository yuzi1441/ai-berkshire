#!/usr/bin/env python3
"""Write a compact release provenance record after all release checks pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


AUTHORITY_INPUTS = (
    "data/investment-dashboard/decision_rules.json",
    "data/investment-dashboard/drift_states.json",
    "data/investment-dashboard/financial_facts.json",
    "data/investment-dashboard/holding_research_reviews.json",
    "data/investment-dashboard/light_thesis_signals.json",
    "data/investment-dashboard/original_buy_theses.json",
    "data/investment-dashboard/post_buy_tracking.json",
)
RECORD_PATHS = (
    "data/investment-dashboard/release_validation.json",
    "site/data/release_validation.json",
)
SCHEMA_VERSION = 2


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_record(root: Path, *, source_sha: str, source_tree: str) -> dict[str, Any]:
    inputs = {
        relative: sha256(root / relative)
        for relative in AUTHORITY_INPUTS
        if (root / relative).is_file()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "source_sha": source_sha,
        "source_tree": source_tree,
        "validated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "validation": "pass",
        "activation": "pending",
        "authority_input_sha256": inputs,
        "report_count": sum(1 for _ in (root / "reports").rglob("*.md")),
    }


def validate_payload(payload: Any, *, source_sha: str, source_tree: str, activated: bool) -> None:
    if (not isinstance(payload, dict) or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != SCHEMA_VERSION):
        raise ValueError("missing or unsupported release validation schema")
    for field, expected in (("source_sha", source_sha), ("source_tree", source_tree)):
        if not re.fullmatch(r"[0-9a-f]{40}", expected) or payload.get(field) != expected:
            raise ValueError(f"release validation {field} mismatch")
    if payload.get("validation") != "pass":
        raise ValueError("release validation did not pass")
    if payload.get("activation") not in ("pending", "pass"):
        raise ValueError("invalid release activation status")
    if activated and payload.get("activation") != "pass":
        raise ValueError("release activation has not completed")
    timestamps = ["validated_at"]
    if payload.get("activation") == "pass":
        timestamps.append("activated_at")
    for field in timestamps:
        value = payload.get(field)
        if not isinstance(value, str) or datetime.fromisoformat(value).utcoffset() is None:
            raise ValueError(f"invalid release validation {field}")
    inputs = payload.get("authority_input_sha256")
    if not isinstance(inputs, dict) or set(inputs) != set(AUTHORITY_INPUTS):
        raise ValueError("incomplete release validation input manifest")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in inputs.values()):
        raise ValueError("invalid release validation input hash")
    if type(payload.get("report_count")) is not int or payload["report_count"] < 0:
        raise ValueError("invalid release validation report count")


def load_record(root: Path, *, source_sha: str, source_tree: str, activated: bool = True) -> dict[str, Any]:
    payloads = [json.loads((root / relative).read_text(encoding="utf-8")) for relative in RECORD_PATHS]
    if payloads[0] != payloads[1]:
        raise ValueError("release validation copies differ")
    if (root / ".source-sha").read_text(encoding="utf-8").strip() != source_sha:
        raise ValueError("release source marker mismatch")
    validate_payload(payloads[0], source_sha=source_sha, source_tree=source_tree, activated=activated)
    # These hashes record inputs at validation time. Runtime jobs legitimately
    # update them later; comparing them with live files would redeploy every tick.
    return payloads[0]


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tree", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="read-only check of a fully activated release")
    mode.add_argument("--activate", action="store_true", help="record successful service activation")
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    try:
        if arguments.check or arguments.activate:
            payload = load_record(root, source_sha=arguments.source_sha, source_tree=arguments.source_tree,
                                  activated=arguments.check)
            if arguments.activate:
                payload.update(activation="pass", activated_at=datetime.now().astimezone().isoformat(timespec="seconds"))
        else:
            payload = build_record(root, source_sha=arguments.source_sha, source_tree=arguments.source_tree)
            validate_payload(payload, source_sha=arguments.source_sha, source_tree=arguments.source_tree, activated=False)
        if not arguments.check:
            for relative in RECORD_PATHS:
                write(root / relative, payload)
    except (OSError, ValueError, TypeError) as exc:
        print(f"release validation record rejected: {exc}")
        return 1
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
