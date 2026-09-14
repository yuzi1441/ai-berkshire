#!/usr/bin/env python3
"""Validate and package one Codex Skill as skill.zip."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


QUICK_VALIDATOR = Path.home() / ".codex/skills/.system/skill-creator/scripts/quick_validate.py"
REPO_VALIDATOR = Path(__file__).resolve().with_name("validate_local_review_skill.py")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    skill = args.skill.resolve()
    output = args.output.resolve()
    if output.name != "skill.zip":
        parser.error("output filename must be skill.zip")
    subprocess.run([sys.executable, str(REPO_VALIDATOR)], check=True)
    if QUICK_VALIDATOR.is_file():
        subprocess.run([sys.executable, str(QUICK_VALIDATOR), str(skill)], check=True)
    files = [path for path in sorted(skill.rglob("*")) if path.is_file()]
    if any(path.is_symlink() for path in skill.rglob("*")):
        raise SystemExit("skill package may not contain symlinks")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, (Path(skill.name) / path.relative_to(skill)).as_posix())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
