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


def argument_value(arguments: argparse.Namespace, name: str) -> str | None:
    """Read optional CLI metadata without breaking older callers/tests."""
    return value_or_none(getattr(arguments, name, None))


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
                "scheduled_for": argument_value(arguments, "scheduled_for"),
                "started_at": timestamp,
                "finished_at": None,
                "duration_seconds": None,
                "message": getattr(arguments, "message", None) or "",
                "run_id": argument_value(arguments, "run_id"),
                "phase": argument_value(arguments, "phase") or "queued",
                "source_sha": argument_value(arguments, "source_sha"),
                "result_id": argument_value(arguments, "result_id"),
            }
        )
    elif arguments.command == "phase":
        phase = argument_value(arguments, "phase")
        if phase:
            current["phase"] = phase
        if argument_value(arguments, "run_id"):
            current["run_id"] = argument_value(arguments, "run_id")
        if argument_value(arguments, "source_sha"):
            current["source_sha"] = argument_value(arguments, "source_sha")
        if argument_value(arguments, "result_id"):
            current["result_id"] = argument_value(arguments, "result_id")
        if getattr(arguments, "message", None) is not None:
            current["message"] = arguments.message or ""
        current.setdefault("job_id", job_id)
        current.setdefault("status", "running")
    else:
        status = getattr(arguments, "status", None) or "ok"
        current.update(
            {
                "job_id": job_id,
                "status": status,
                "finished_at": timestamp,
                "completed_at": timestamp,
                "duration_seconds": getattr(arguments, "duration", None),
                "data_cutoff": argument_value(arguments, "data_cutoff"),
                "record_count": getattr(arguments, "record_count", None),
                "failed_count": getattr(arguments, "failed_count", None),
                "message": getattr(arguments, "message", None) or "",
                "phase": argument_value(arguments, "phase") or ("complete" if status in {"ok", "partial", "deferred"} else "failed"),
            }
        )
        for field in ("run_id", "source_sha", "result_id"):
            value = argument_value(arguments, field)
            if value:
                current[field] = value
        if status == "ok":
            current["last_success_at"] = timestamp
            current["last_success_status"] = status
    jobs[job_id] = current
    payload["schema_version"] = 2
    payload["updated_at"] = timestamp
    write(path, payload)
    return 0


def normalize_contract(path: Path, template: Path) -> int:
    """Refresh the schedule contract while preserving runtime job history."""
    payload = load(path)
    contract = load(template)
    schedules = contract.get("schedules", [])
    if not isinstance(schedules, list):
        raise ValueError(f"invalid schedule contract: {template}")
    active_job_ids = {
        schedule.get("job_id")
        for schedule in schedules
        if isinstance(schedule, dict) and schedule.get("job_id")
    }
    jobs = payload.get("jobs", {})
    payload["schedules"] = schedules
    payload["jobs"] = {
        job_id: jobs[job_id]
        for job_id in active_job_ids
        if job_id in jobs and isinstance(jobs[job_id], dict)
    }
    payload["schema_version"] = max(int(payload.get("schema_version") or 1), 2)
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
    start.add_argument("--run-id")
    start.add_argument("--phase")
    start.add_argument("--source-sha")
    start.add_argument("--result-id")
    phase = subparsers.add_parser("phase")
    phase.add_argument("--job-id", required=True)
    phase.add_argument("--phase", required=True)
    phase.add_argument("--message")
    phase.add_argument("--run-id")
    phase.add_argument("--source-sha")
    phase.add_argument("--result-id")
    finish = subparsers.add_parser("finish")
    finish.add_argument("--job-id", required=True)
    finish.add_argument(
        "--status",
        choices=("ok", "partial", "deferred", "interrupted", "error", "skipped"),
        default="ok",
    )
    finish.add_argument("--duration", type=float)
    finish.add_argument("--data-cutoff")
    finish.add_argument("--record-count", type=int)
    finish.add_argument("--failed-count", type=int)
    finish.add_argument("--message")
    finish.add_argument("--run-id")
    finish.add_argument("--phase")
    finish.add_argument("--source-sha")
    finish.add_argument("--result-id")
    normalize = subparsers.add_parser("normalize")
    normalize.add_argument("--template", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        if arguments.command == "normalize":
            return normalize_contract(arguments.path.resolve(), arguments.template.resolve())
        return update(arguments)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
