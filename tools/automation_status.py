#!/usr/bin/env python3
"""Maintain one machine-readable status manifest for dashboard automation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")
DEFAULT_PATH = ROOT / "data" / "investment-dashboard" / "automation_status.json"


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "updated_at": None, "jobs": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid automation status: {path}: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs", {}), dict):
        raise ValueError(f"invalid automation status shape: {path}")
    return payload


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    site_path = path.parents[2] / "site" / "data" / path.name
    site_path.parent.mkdir(parents=True, exist_ok=True)
    site_temporary = site_path.with_suffix(site_path.suffix + ".tmp")
    site_temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    site_temporary.replace(site_path)


def value_or_none(value: str | None) -> str | None:
    return value if value not in {None, "", "null"} else None


def update(arguments: argparse.Namespace) -> int:
    path = arguments.path.resolve()
    payload = load(path)
    jobs = payload.setdefault("jobs", {})
    job_id = arguments.job_id
    current = jobs.get(job_id) if isinstance(jobs.get(job_id), dict) else {}
    timestamp = now_iso()
    if arguments.command == "start":
        current.update(
            {
                "job_id": job_id,
                "status": "running",
                "scheduled_for": value_or_none(arguments.scheduled_for),
                "started_at": timestamp,
                "finished_at": None,
                "duration_seconds": None,
                "message": arguments.message or "",
            }
        )
    else:
        status = arguments.status or "ok"
        current.update(
            {
                "job_id": job_id,
                "status": status,
                "finished_at": timestamp,
                "duration_seconds": arguments.duration,
                "data_cutoff": value_or_none(arguments.data_cutoff),
                "record_count": arguments.record_count,
                "failed_count": arguments.failed_count,
                "message": arguments.message or "",
            }
        )
        if status in {"ok", "partial"}:
            current["last_success_at"] = timestamp
            current["last_success_status"] = status
    jobs[job_id] = current
    payload["schema_version"] = 1
    payload["updated_at"] = timestamp
    write(path, payload)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("--job-id", required=True)
    start.add_argument("--scheduled-for")
    start.add_argument("--message")
    finish = subparsers.add_parser("finish")
    finish.add_argument("--job-id", required=True)
    finish.add_argument("--status", choices=("ok", "partial", "error", "skipped"), default="ok")
    finish.add_argument("--duration", type=float)
    finish.add_argument("--data-cutoff")
    finish.add_argument("--record-count", type=int)
    finish.add_argument("--failed-count", type=int)
    finish.add_argument("--message")
    arguments = parser.parse_args()
    try:
        return update(arguments)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
