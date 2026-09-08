"""Repository-local evidence reference contract for persisted formal Drift."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def normalize_facts_source(repo_root: Path, raw: str) -> str:
    root = repo_root.resolve()
    path = Path(str(raw))
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(
            f"facts source must be archived inside the repository first: {raw}; "
            "use research/sources/..."
        )
    if not resolved.is_file():
        raise ValueError(f"facts source does not exist: {raw}")
    return resolved.relative_to(root).as_posix()


def validate_drift_facts_sources(repo_root: Path, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    companies = payload.get("companies")
    if not isinstance(companies, dict):
        return ["drift_states.companies must be an object"]

    def check(ticker: str, label: str, record: dict[str, Any]) -> None:
        sources = record.get("facts_sources")
        if not isinstance(sources, list):
            errors.append(f"{ticker} {label} facts_sources must be a list")
            return
        for raw in sources:
            if not isinstance(raw, str) or not raw.strip():
                errors.append(f"{ticker} {label} has invalid facts_source")
                continue
            if Path(raw).is_absolute():
                errors.append(f"{ticker} {label} facts_source must be repo-relative: {raw}")
                continue
            try:
                normalize_facts_source(repo_root, raw)
            except ValueError as error:
                errors.append(f"{ticker} {label}: {error}")

    for ticker, record in companies.items():
        if not isinstance(record, dict):
            errors.append(f"{ticker} drift record must be an object")
            continue
        check(str(ticker), "current", record)
        history = record.get("review_history", [])
        if not isinstance(history, list):
            errors.append(f"{ticker} review_history must be a list")
            continue
        for index, historical in enumerate(history):
            if not isinstance(historical, dict):
                errors.append(f"{ticker} review_history[{index}] must be an object")
                continue
            check(str(ticker), f"review_history[{index}]", historical)
    return errors
