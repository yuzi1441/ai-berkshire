#!/usr/bin/env python3
"""Validate one staged local daily-review transaction."""
import argparse
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo-root", type=Path, required=True)
parser.add_argument("--date", required=True)
parser.add_argument("--force", action="store_true")
args = parser.parse_args()
root = args.repo_root.resolve()
transaction = root / ".runtime/local-review" / args.date
command = [
    sys.executable, str(root / "tools/local_daily_review.py"), "validate",
    "--repo-root", str(root), "--input-root", str(transaction / "input"),
    "--reviews-dir", str(transaction / "reviews"),
    "--output-root", str(transaction / "validated"),
]
if args.force:
    command.append("--force")
raise SystemExit(subprocess.call(command, cwd=root))
