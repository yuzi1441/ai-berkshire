#!/usr/bin/env python3
"""Publish deterministic daily-review packets to the generated-data branch."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import local_daily_review  # noqa: E402


class PublishInputError(RuntimeError):
    pass


def run(args: list[str], *, cwd: Path, capture: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, check=False, capture_output=capture, text=True)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise PublishInputError(f"{' '.join(args)} failed: {detail}")
    return completed


def publish(input_root: Path, remote: str, branch: str, *, work_root: Path | None = None) -> dict[str, object]:
    manifest, _ = local_daily_review.validate_input(input_root)
    temporary_parent = work_root or Path(tempfile.mkdtemp(prefix="local-review-input-publish-"))
    owns_parent = work_root is None
    temporary_parent.mkdir(parents=True, exist_ok=True)
    checkout = temporary_parent / "checkout"
    try:
        run(["git", "clone", "--quiet", "--single-branch", "--branch", branch, remote, str(checkout)], cwd=temporary_parent)
        relative_root = Path("data/local-daily-review/input") / str(manifest["date"])
        destination = checkout / relative_root
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(input_root, destination)
        pointer = {
            "schema_version": 1,
            "status": "awaiting_local_review",
            "date": manifest["date"],
            "path": relative_root.as_posix(),
            "manifest_sha256": manifest["manifest_sha256"],
            "source_sha": manifest["source_sha"],
            "market": local_daily_review.MARKET,
            "external_llm_required": False,
        }
        local_daily_review.write_json(checkout / "data/local-daily-review/input/latest.json", pointer)
        paths = [relative_root.as_posix(), "data/local-daily-review/input/latest.json"]
        run(["git", "add", "--", *paths], cwd=checkout)
        changed = run(["git", "diff", "--cached", "--name-only", "-z"], cwd=checkout, capture=True).stdout
        changed_paths = {item for item in changed.split("\0") if item}
        if any(not item.startswith("data/local-daily-review/input/") for item in changed_paths):
            raise PublishInputError("staged path escaped deterministic input boundary")
        if not changed_paths:
            return {"status": "unchanged", "date": manifest["date"], "branch": branch, "files": 0}
        run(["git", "-c", "user.name=AI Berkshire VPS", "-c", "user.email=vps@ai-berkshire.local",
             "commit", "-m", f"chore: prepare local daily review {manifest['date']}"], cwd=checkout)
        run(["git", "push", "origin", branch], cwd=checkout)
        commit = run(["git", "rev-parse", "HEAD"], cwd=checkout, capture=True).stdout.strip()
        return {"status": "published", "date": manifest["date"], "branch": branch,
                "commit": commit, "files": len(changed_paths)}
    finally:
        if owns_parent:
            shutil.rmtree(temporary_parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--remote", default=os.environ.get("AI_BERKSHIRE_ORIGIN_URL", "https://github.com/yuzi1441/ai-berkshire.git"))
    parser.add_argument("--branch", default=os.environ.get("AI_BERKSHIRE_GENERATED_BRANCH", "vps-generated"))
    args = parser.parse_args()
    try:
        print(json.dumps(publish(args.input_root.resolve(), args.remote, args.branch), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, PublishInputError, local_daily_review.LocalReviewError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
