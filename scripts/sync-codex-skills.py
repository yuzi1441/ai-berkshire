#!/usr/bin/env python3
"""Generate Codex skills from AI Berkshire Claude command files."""

from __future__ import annotations

import re
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = ROOT / "skills"
CODEX_SKILLS = ROOT / "codex-skills"


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 5 :].lstrip("\n")


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def yaml_quote(value: str) -> str:
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def metadata_for(name: str, source_name: str, source_text: str) -> str:
    existing, body = split_frontmatter(source_text)
    if existing:
        has_name = re.search(r"(?m)^name:\s*", existing) is not None
        has_description = re.search(r"(?m)^description:\s*", existing) is not None
        lines = []
        if not has_name:
            lines.append(f"name: {name}")
        if not has_description:
            title = first_heading(body, name)
            lines.append(
                "description: "
                + yaml_quote(f"AI Berkshire skill: {title}. Source: skills/{source_name}.")
            )
        lines.append(existing.rstrip())
        return "---\n" + "\n".join(lines) + "\n---\n\n"

    title = first_heading(source_text, name)
    description = f"AI Berkshire skill: {title}. Source: skills/{source_name}."
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {yaml_quote(description)}\n"
        "---\n\n"
    )


def codex_body(name: str, source_name: str, source_text: str) -> str:
    _, body = split_frontmatter(source_text)
    note = (
        "## Codex adapter note\n\n"
        f"This skill is generated from `skills/{source_name}` so Claude Code "
        "and Codex users share one canonical workflow.\n\n"
        "- Treat `$ARGUMENTS` as the user's request in the current Codex thread.\n"
        "- When the source mentions Claude-only surfaces such as Task, Agent, "
        "WebSearch, Bash, Read, or Write, use the closest Codex capability "
        "available in this session: subagents when available, web search when "
        "needed, shell commands for local tools, and normal file edits for "
        "workspace files.\n"
        "- Use shared project tools from `tools/` in this repository. Prefer "
        "running commands from the repository root with paths like "
        "`python3 tools/financial_rigor.py ...`; if the current thread starts "
        "outside the repo, locate the actual checkout path first instead of "
        "assuming a fixed home-directory path.\n"
        "- Before starting research, run the `date` command to confirm "
        "today's date; treat it as the baseline for \"latest\" data and state "
        "the data cutoff date in the report header. Never assume the current "
        "date from training data.\n"
        "- Preserve the research quality rules from `AGENTS.md`: cross-check "
        "financial data, use exact arithmetic tools for valuation/math, and "
        "clearly label uncertainty and source gaps.\n\n"
    )
    return note + body.rstrip() + "\n"


def main() -> None:
    check = "--check" in sys.argv[1:]
    check_installed = "--check-installed" in sys.argv[1:]
    install_root_arg = next(
        (arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--install-root=")),
        None,
    )
    unknown_args = [
        arg for arg in sys.argv[1:]
        if arg not in {"--check", "--check-installed"} and not arg.startswith("--install-root=")
    ]
    if unknown_args:
        joined = ", ".join(unknown_args)
        raise SystemExit(f"Unknown argument(s): {joined}")

    if not check and not check_installed:
        CODEX_SKILLS.mkdir(exist_ok=True)

    count = 0
    stale: list[str] = []
    for source in sorted(CLAUDE_SKILLS.glob("*.md")):
        name = source.stem
        source_text = source.read_text(encoding="utf-8")
        target_dir = CODEX_SKILLS / name
        target = target_dir / "SKILL.md"
        content = metadata_for(name, source.name, source_text) + codex_body(
            name, source.name, source_text
        )
        comparison_target = target
        if check_installed:
            codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            install_root = Path(install_root_arg) if install_root_arg else codex_home / "skills"
            comparison_target = install_root / name / "SKILL.md"
        if check or check_installed:
            if not comparison_target.exists() or comparison_target.read_text(encoding="utf-8") != content:
                try:
                    display = str(comparison_target.relative_to(ROOT))
                except ValueError:
                    display = str(comparison_target)
                stale.append(display)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        count += 1

    if check or check_installed:
        if stale:
            label = "Installed Codex skills" if check_installed else "Codex skills"
            print(f"{label} are out of date:")
            for path in stale:
                print(f"  {path}")
            raise SystemExit(1)
        if check_installed:
            print(f"Checked {count} installed Codex skills")
        else:
            print(f"Checked {count} Codex skills in {CODEX_SKILLS.relative_to(ROOT)}")
        return

    print(f"Generated {count} Codex skills in {CODEX_SKILLS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
