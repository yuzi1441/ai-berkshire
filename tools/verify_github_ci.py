#!/usr/bin/env python3
"""Fail closed unless the target Git SHA has a successful full push CI run."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_REPOSITORY = "yuzi1441/ai-berkshire"
DEFAULT_WORKFLOW = "Investment dashboard"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def fetch_runs(repository: str, sha: str, *, token: str | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode({"head_sha": sha, "event": "push", "per_page": 50})
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/runs?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-berkshire-release-gate/1.0",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("GitHub Actions response must be an object")
    return payload


def classify(payload: dict[str, Any], *, sha: str, workflow: str) -> dict[str, Any]:
    matching = [
        run for run in payload.get("workflow_runs", [])
        if isinstance(run, dict)
        and run.get("head_sha") == sha
        and run.get("event") == "push"
        and run.get("name") == workflow
    ]
    matching.sort(key=lambda run: str(run.get("created_at") or ""), reverse=True)
    if not matching:
        return {"status": "no_checks", "reason": "no matching push workflow run"}
    run = matching[0]
    if run.get("status") != "completed":
        status = "pending"
    elif run.get("conclusion") == "success":
        status = "pass"
    else:
        status = "fail"
    return {
        "status": status,
        "run_id": run.get("id"),
        "run_url": run.get("html_url"),
        "workflow": run.get("name"),
        "conclusion": run.get("conclusion"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW)
    parser.add_argument("--fixture", type=Path)
    arguments = parser.parse_args()
    sha = arguments.sha.lower()
    if not SHA_RE.fullmatch(sha):
        raise SystemExit("--sha must be a full 40-character Git SHA")
    payload = (
        json.loads(arguments.fixture.read_text(encoding="utf-8"))
        if arguments.fixture
        else fetch_runs(arguments.repository, sha, token=os.environ.get("GITHUB_TOKEN"))
    )
    result = classify(payload, sha=sha, workflow=arguments.workflow)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
