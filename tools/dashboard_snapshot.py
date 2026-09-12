"""Atomic, content-identified dashboard core (derived output, never authority)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

FILENAME = "dashboard_core.json"


def snapshot_digest(payload: dict[str, Any]) -> str:
    content = {key: value for key, value in payload.items() if key != "generation_id"}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def make_snapshot(*, board, layers, tracking, original_theses) -> dict[str, Any]:
    """Bind state, evaluated rules and holding identities in one HTTP response."""
    result = {
        "schema_version": 1,
        "artifact_role": "derived_dashboard_core",
        "board": {key: board.get(key) for key in ("generated_at", "as_of", "data_health")},
        "companyState": layers["state"],
        "rules": layers["rules"],
        "technical": layers["technical"],
        "tracking": tracking,
        "originalTheses": original_theses,
    }
    # Runtime state refreshes have their own generation, even at the same SHA.
    result["board"]["report_built_at"] = board.get("generated_at")
    result["board"]["generated_at"] = layers["state"].get("generated_at") or board.get("generated_at")
    result["generation_id"] = snapshot_digest(result)
    validate_snapshot(result)
    return result


def validate_snapshot(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1 or payload.get("artifact_role") != "derived_dashboard_core":
        raise ValueError("unsupported dashboard core")
    if payload.get("generation_id") != snapshot_digest(payload):
        raise ValueError("dashboard core content hash mismatch")
    populations = []
    for key in ("companyState", "rules"):
        rows = payload.get(key, {}).get("companies")
        if not isinstance(rows, list):
            raise ValueError(f"dashboard core missing {key}")
        tickers = [row.get("ticker") for row in rows if isinstance(row, dict)]
        if len(tickers) != len(rows) or any(not t for t in tickers) or len(set(tickers)) != len(tickers):
            raise ValueError(f"dashboard core invalid {key} identities")
        populations.append(set(tickers))
    if populations[0] != populations[1]:
        raise ValueError("dashboard core state/rule population mismatch")


def publish_snapshot(path: Path, **inputs) -> dict[str, Any]:
    payload = make_snapshot(**inputs)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Readers see the old complete file or the new complete file, never a mix.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".dashboard-core-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Static assets are read by the web-server user, not the build user.
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return payload
