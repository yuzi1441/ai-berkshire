#!/usr/bin/env python3
"""Fail-closed structural and external-LLM boundary checks for the local review Skill."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "codex-skills/daily-investment-review"
PYTHON_FILES = [ROOT / "tools/local_daily_review.py", ROOT / "scripts/publish_local_review_inputs.py",
                *sorted((SKILL / "scripts").glob("*.py"))]
FORBIDDEN_IMPORTS = {"anthropic", "httpx", "openai", "requests"}
FORBIDDEN_ENDPOINTS = ("api.deepseek.com", "api.openai.com", "api.anthropic.com")


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    skill_md = SKILL / "SKILL.md"
    if not skill_md.is_file() or not (SKILL / "agents/openai.yaml").is_file():
        fail("daily-investment-review package is incomplete")
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"---\n(?P<meta>.*?)\n---\n", text, re.DOTALL)
    if not match or "name: daily-investment-review" not in match.group("meta") or "description:" not in match.group("meta"):
        fail("daily-investment-review frontmatter is invalid")
    for path in SKILL.rglob("*"):
        if path.is_symlink():
            fail(f"Skill symlink is not allowed: {path}")
    for path in PYTHON_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            if any(module.split(".", 1)[0] in FORBIDDEN_IMPORTS for module in modules):
                fail(f"external LLM/network client import is forbidden: {path}")
        source = path.read_text(encoding="utf-8").casefold()
        if any(endpoint in source for endpoint in FORBIDDEN_ENDPOINTS):
            fail(f"external LLM endpoint is forbidden: {path}")
    print(f"local review Skill boundary=PASS files={len(PYTHON_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
