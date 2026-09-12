#!/usr/bin/env python3
"""Generate Codex custom prompts from AI Berkshire skills.

Codex custom prompts are deprecated in favor of skills, but they provide the
slash-command style entry point that Claude Code users expect.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = ROOT / "skills"
CODEX_PROMPTS = ROOT / "codex-prompts"


def split_frontmatter(text: str):
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


def prompt_for(source: Path) -> str:
    name = source.stem
    source_text = source.read_text(encoding="utf-8")
    _, body = split_frontmatter(source_text)
    title = first_heading(body, name)
    description = f"AI Berkshire slash entry for {title}."
    return (
        "---\n"
        f"description: {yaml_quote(description)}\n"
        "argument-hint: $ARGUMENTS\n"
        "---\n\n"
        f"Use the installed AI Berkshire Codex skill `{name}` for this request.\n\n"
        f"If the skill is not already loaded, locate the actual repository checkout "
        f"and read `codex-skills/{name}/SKILL.md`; do not assume a fixed home-directory path.\n\n"
        "User arguments:\n"
        "$ARGUMENTS\n"
    )


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
        CODEX_PROMPTS.mkdir(exist_ok=True)

    count = 0
    stale: list[str] = []
    for source in sorted(CLAUDE_SKILLS.glob("*.md")):
        target = CODEX_PROMPTS / source.name
        content = prompt_for(source)
        comparison_target = target
        if check_installed:
            codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            install_root = Path(install_root_arg) if install_root_arg else codex_home / "prompts"
            comparison_target = install_root / source.name
        if check or check_installed:
            if not comparison_target.exists() or comparison_target.read_text(encoding="utf-8") != content:
                try:
                    display = str(comparison_target.relative_to(ROOT))
                except ValueError:
                    display = str(comparison_target)
                stale.append(display)
        else:
            target.write_text(content, encoding="utf-8")
        count += 1

    if check or check_installed:
        if stale:
            label = "Installed Codex prompts" if check_installed else "Codex prompts"
            print(f"{label} are out of date:")
            for path in stale:
                print(f"  {path}")
            raise SystemExit(1)
        if check_installed:
            print(f"Checked {count} installed Codex prompts")
        else:
            print(f"Checked {count} Codex prompts in {CODEX_PROMPTS.relative_to(ROOT)}")
        return

    print(f"Generated {count} Codex prompts in {CODEX_PROMPTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
