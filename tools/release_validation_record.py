#!/usr/bin/env python3
"""Write a compact release provenance record after all release checks pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_record(root: Path, *, source_sha: str, source_tree: str) -> dict[str, Any]:
    inputs = {
        relative: sha256(root / relative)
        for relative in AUTHORITY_INPUTS
        if (root / relative).is_file()
    }
    return {
        "schema_version": 1,
        "source_sha": source_sha,
        "source_tree": source_tree,
        "validated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "validation": "pass",
        "authority_input_sha256": inputs,
        "report_count": sum(1 for _ in (root / "reports").rglob("*.md")),
    }


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
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    payload = build_record(root, source_sha=arguments.source_sha, source_tree=arguments.source_tree)
    for relative in (
        "data/investment-dashboard/release_validation.json",
        "site/data/release_validation.json",
    ):
        write(root / relative, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
