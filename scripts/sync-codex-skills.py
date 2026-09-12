#!/usr/bin/env python3
"""Generate Codex skills from AI Berkshire Claude command files."""

from __future__ import annotations

import argparse
import hashlib
import re
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


def package_manifest(package: Path) -> dict[str, str]:
    """Hash every installed package file, including auxiliary and hidden files.

    Symlinks are rejected: following directory links could silently omit files
    or compare content outside the package being installed.
    """
    if package.is_symlink() or not package.is_dir():
        raise ValueError(f"not a regular package directory: {package}")
    manifest = {}
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"package symlink is unsupported: {path}")
        if path.is_file():
            manifest[path.relative_to(package).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.is_dir():
            raise ValueError(f"unsupported package entry: {path}")
    if "SKILL.md" not in manifest:
        raise ValueError(f"package has no SKILL.md: {package}")
    return manifest


def check_installed_packages(install_root: Path) -> tuple[int, int, list[str]]:
    """Compare repository-owned packages only; unrelated user skills are allowed."""
    packages = sorted(path for path in CODEX_SKILLS.iterdir() if path.is_dir() or path.is_symlink())
    if not packages:
        raise ValueError(f"no skill packages found in {CODEX_SKILLS}")
    stale = []
    file_count = 0
    for package in packages:
        expected = package_manifest(package)
        file_count += len(expected)
        try:
            actual = package_manifest(install_root / package.name)
        except (OSError, ValueError) as exc:
            stale.append(str(exc))
            continue
        for relative in sorted(expected.keys() | actual.keys()):
            if expected.get(relative) != actual.get(relative):
                kind = "missing" if relative not in actual else "unexpected" if relative not in expected else "changed"
                stale.append(f"{kind}: {install_root / package.name / relative}")
    return len(packages), file_count, stale


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check canonical generation without writing")
    parser.add_argument("--check-installed", action="store_true", help="compare complete installed package manifests")
    parser.add_argument("--install-root", type=Path)
    args = parser.parse_args()
    if args.install_root is not None and not args.check_installed:
        parser.error("--install-root requires --check-installed")
    check, check_installed = args.check, args.check_installed

    installed_stale = []
    if check_installed:
        codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        install_root = args.install_root if args.install_root is not None else codex_home / "skills"
        try:
            package_count, file_count, installed_stale = check_installed_packages(install_root)
        except (OSError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        if installed_stale:
            print("Installed Codex package manifests differ:\n  " + "\n  ".join(installed_stale))
        else:
            print(f"Checked {package_count} installed Codex packages ({file_count} files)")
        if not check:
            if installed_stale:
                raise SystemExit(1)
            return

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
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != content:
                stale.append(str(target.relative_to(ROOT)))
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        count += 1

    if check:
        if stale:
            print("Canonical Codex skills are out of date:")
            for path in stale:
                print(f"  {path}")
            raise SystemExit(1)
        print(f"Checked {count} Codex skills in {CODEX_SKILLS.relative_to(ROOT)}")
        if installed_stale:
            raise SystemExit(1)
        return

    print(f"Generated {count} Codex skills in {CODEX_SKILLS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
