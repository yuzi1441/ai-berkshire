#!/usr/bin/env python3
"""Sync and verify the latest deterministic local-review input."""
import argparse
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo-root", type=Path, required=True)
parser.add_argument("--ticker", action="append")
args = parser.parse_args()
root = args.repo_root.resolve()
command = [
    sys.executable, str(root / "tools/local_daily_review.py"), "sync-input",
    "--repo-root", str(root), "--runtime-root", str(root / ".runtime/local-review"),
]
if args.ticker:
    raise SystemExit("--ticker requires an already synced full input; use local_daily_review.py prepare for a partial dry-run")
raise SystemExit(subprocess.call(command, cwd=root))
