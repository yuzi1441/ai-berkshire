#!/usr/bin/env python3
"""Manage explicit lifecycle and Drift overrides without touching holdings."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import decision_state  # noqa: E402


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    lifecycle = sub.add_parser("set-lifecycle")
    lifecycle.add_argument("ticker")
    lifecycle.add_argument("lifecycle", choices=("WATCH", "PRE_BUY", "EXITED"))
    lifecycle.add_argument("--reason", default="manual override")
    drift = sub.add_parser("set-drift")
    drift.add_argument("ticker")
    drift.add_argument("direction", choices=("improved", "unchanged", "weakened", "unknown"))
    drift.add_argument("--severity", choices=("none", "minor", "major", "unknown"), default="none")
    drift.add_argument("--summary", default="")
    drift.add_argument("--next-review")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    data = root / "data" / "investment-dashboard"
    if args.command == "set-lifecycle":
        path = data / decision_state.OVERRIDES_RELATIVE.name
        payload = decision_state.load_json(path, {"schema_version": 1, "companies": {}})
        payload.setdefault("schema_version", 1)
        payload.setdefault("companies", {})[args.ticker.upper()] = {
            "lifecycle": args.lifecycle,
            "reason": args.reason,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        _save(path, payload)
        print(f"Saved lifecycle override {args.ticker.upper()} -> {args.lifecycle}; HOLDING must be registered via post_buy_tracking.")
        return 0
    path = data / decision_state.DRIFT_RELATIVE.name
    payload = decision_state.load_json(path, {"schema_version": 1, "companies": {}})
    payload.setdefault("schema_version", 1)
    payload.setdefault("companies", {})[args.ticker.upper()] = {
        "direction": args.direction,
        "severity": args.severity,
        "summary": args.summary,
        "last_checked": datetime.now().astimezone().isoformat(timespec="seconds"),
        "next_review": args.next_review,
        "source": "manual",
    }
    _save(path, payload)
    print(f"Saved Drift state {args.ticker.upper()} -> {args.direction}/{args.severity}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
