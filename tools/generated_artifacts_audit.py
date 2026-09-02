#!/usr/bin/env python3
"""Read-only audit of generated artifacts, source state, and Git changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str, root: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def _status(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = result.stdout
    for line in output.split("\0"):
        if len(line) < 4:
            continue
        code = line[:2]
        raw_path = line[3:]
        path = raw_path.split(" -> ", 1)[-1]
        rows.append({"code": code, "path": path, "untracked": code == "??"})
    return rows


def _category(path: str) -> str:
    p = Path(path)
    if path.startswith("reports/"):
        return "reports"
    if path.startswith("site/data/"):
        return "site_data_generated"
    if path.startswith("data/"):
        return "data_generated"
    if path.startswith("logs/"):
        return "logs_or_runtime_artifacts"
    if path.startswith(("skills/", "codex-skills/", "codex-prompts/")) or p.name in {"CLAUDE.md", "AGENTS.md"}:
        return "skills"
    if path.startswith(("tools/", "scripts/", "deploy/")) and p.suffix.lower() in {".py", ".js", ".mjs", ".sh", ".bat"}:
        return "core_code"
    if path.startswith("tests/"):
        return "test_code"
    if p.name == ".gitignore" or p.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini", ".conf"} or path.startswith(("config/", "schemas/")):
        return "schema_or_config"
    return "other"


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _duplicate_audit(root: Path) -> dict[str, Any]:
    data_dir = root / "data" / "investment-dashboard"
    site_dir = root / "site" / "data"
    common = 0
    identical = 0
    different: list[str] = []
    if data_dir.is_dir() and site_dir.is_dir():
        for source in sorted(data_dir.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(data_dir)
            deployed = site_dir / relative
            if not deployed.is_file():
                continue
            common += 1
            if _file_digest(source) == _file_digest(deployed):
                identical += 1
            else:
                different.append(relative.as_posix())
    return {"common_files": common, "byte_identical": identical, "intentionally_transformed_or_different": different}


def _policy(root: Path) -> dict[str, Any]:
    return {
        "must_commit_source_of_truth": [
            "reports/** (canonical research; no mass rewrite or deletion)",
            "data/investment-dashboard/decision_rules.json",
            "data/investment-dashboard/company_state.json",
            "data/investment-dashboard/drift_states.json",
            "data/investment-dashboard/post_buy_tracking.json",
            "data/investment-dashboard/original_buy_theses.json",
            "data/investment-dashboard/rule_lifecycle.json",
            "data/investment-dashboard/rule_change_log.json",
        ],
        "rebuildable_deploy_artifacts": [
            "site/data/**",
            "data/investment-dashboard/decision_board.json",
            "data/investment-dashboard/decision_details/**",
            "data/investment-dashboard/reports_catalog.json",
            "data/investment-dashboard/report_history.json",
        ],
        "ignore_or_keep_out_of_long_term_git": [
            "data/sentiment/snapshots/**",
            "data/technical-backtest/cache/**",
            "data/sentiment/work-in-progress.json",
            "logs/** runtime and command logs",
        ],
        "preserve_history": [
            "reports/**",
            "data/investment-dashboard/original_buy_theses.json",
            "retired Rules inside decision_rules.json",
            "data/investment-dashboard/rule_change_log.json",
            "data/investment-dashboard/report_history.json",
        ],
        "note": "Current CI and VPS builds regenerate site/data; this audit does not delete or untrack existing files.",
    }


def audit(root: Path = ROOT) -> dict[str, Any]:
    rows = _status(root)
    counts = Counter(_category(row["path"]) for row in rows)
    untracked = [row["path"] for row in rows if row["untracked"]]
    generated = [
        row["path"]
        for row in rows
        if row["path"].startswith(("data/", "site/data/", "logs/"))
    ]
    report_paths = [row["path"] for row in rows if row["path"].startswith("reports/")]
    report_diff = _git("diff", "--numstat", "--", "reports", root=root).splitlines()
    return {
        "repo": str(root),
        "git_status_entries": len(rows),
        "category_counts": dict(sorted(counts.items())),
        "untracked_count": len(untracked),
        "untracked_paths": untracked,
        "generated_paths_in_status": generated,
        "report_paths_in_status": report_paths,
        "report_diff_numstat_lines": report_diff,
        "data_site_duplicate_audit": _duplicate_audit(root),
        "policy": _policy(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo_root.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
