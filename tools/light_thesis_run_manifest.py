#!/usr/bin/env python3
"""Local operator-declared batch metadata; never invokes models or writes authority."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

AUTHORITY = Path("data/investment-dashboard/light_thesis_signals.json")
LOGS = Path("logs/light-thesis-runs")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")


def log_path(root, run_id, completed=False):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", run_id):
        raise ValueError("invalid run_id")
    return root / LOGS / (run_id + ("-completed" if completed else "-started") + ".json")


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def authority_sha(root):
    return hashlib.sha256((root / AUTHORITY).read_bytes()).hexdigest()


def save_new(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def start(root, run_id, *, model, reasoning_effort, eligible):
    if not model.strip() or reasoning_effort not in EFFORTS:
        raise ValueError("model and explicit reasoning_effort are required")
    if type(eligible) is not int or eligible < 1:
        raise ValueError("eligible must be a positive integer")
    return save_new(log_path(root, run_id), {
        "run_type": "light_thesis_fresh_evidence",
        "run_id": run_id,
        "model": model.strip(),
        "reasoning_effort": reasoning_effort,
        "metadata_source": "operator_declared",
        "execution_environment": "codex_client",
        "started_at": timestamp(),
        "completed_at": None,
        "eligible": eligible,
        "success": None,
        "failed": None,
        "authority_sha256": authority_sha(root),
    })


def complete(root, run_id, *, success, failed):
    payload = json.loads(log_path(root, run_id).read_text(encoding="utf-8"))
    if any(type(n) is not int or n < 0 for n in (success, failed)):
        raise ValueError("counts must be non-negative integers")
    if success + failed != payload["eligible"]:
        raise ValueError("success + failed must equal eligible")
    payload.update(completed_at=timestamp(), success=success, failed=failed,
                   authority_sha256=authority_sha(root))
    return save_new(log_path(root, run_id, completed=True), payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start")
    begin.add_argument("--run-id", required=True)
    begin.add_argument("--model", required=True)
    begin.add_argument("--reasoning-effort", required=True, choices=EFFORTS)
    begin.add_argument("--eligible", required=True, type=int)
    end = commands.add_parser("complete")
    end.add_argument("--run-id", required=True)
    end.add_argument("--success", required=True, type=int)
    end.add_argument("--failed", required=True, type=int)
    args = parser.parse_args()
    if args.command == "start":
        result = start(args.repo_root.resolve(), args.run_id, model=args.model,
                       reasoning_effort=args.reasoning_effort, eligible=args.eligible)
    else:
        result = complete(args.repo_root.resolve(), args.run_id,
                          success=args.success, failed=args.failed)
    print(result)


if __name__ == "__main__":
    main()
