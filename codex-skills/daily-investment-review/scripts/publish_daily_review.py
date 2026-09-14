#!/usr/bin/env python3
"""Apply and exact-stage an explicitly approved validated local review."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo-root", type=Path, required=True)
parser.add_argument("--date", required=True)
parser.add_argument("--stage-only", action="store_true")
args = parser.parse_args()
root = args.repo_root.resolve()

def output(command):
    return subprocess.run(command, cwd=root, check=True, capture_output=True, text=True).stdout.strip()

branch = output(["git", "branch", "--show-current"])
if not args.stage_only and branch != "main":
    raise SystemExit(f"publish requires main; current branch is {branch or 'detached'}")
transaction = root / ".runtime/local-review" / args.date
subprocess.run([sys.executable, str(root / "tools/local_daily_review.py"), "apply",
                "--repo-root", str(root), "--validated-root", str(transaction / "validated")],
               cwd=root, check=True)
dated = f"data/local-daily-review/published/{args.date}"
exact = [f"{dated}/sentiment.json", f"{dated}/opportunity_scans.json",
         "data/local-daily-review/published/latest.json"]
subprocess.run(["git", "add", "--", *exact], cwd=root, check=True)
staged = set(filter(None, output(["git", "diff", "--cached", "--name-only"]).splitlines()))
if staged != set(exact):
    raise SystemExit("staged paths are not exact: " + json.dumps(sorted(staged)))
if args.stage_only:
    print(json.dumps({"status": "staged", "files": exact}, ensure_ascii=False))
    raise SystemExit(0)
subprocess.run(["git", "commit", "-m", f"Publish local daily investment review {args.date}"], cwd=root, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=root, check=True)
print(json.dumps({"status": "pushed", "commit": output(["git", "rev-parse", "HEAD"])}, ensure_ascii=False))
