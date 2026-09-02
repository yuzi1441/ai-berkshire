"""Stable source fingerprints shared by report and dashboard workflows.

Git checkouts may expose the same text with LF on macOS and CRLF on Windows.
Review rules are bound to report content, not to the checkout's newline style,
so text fingerprints normalise BOMs and line endings before hashing.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def canonical_text_bytes(payload: bytes) -> bytes:
    """Return UTF-8 text with a stable BOM/newline representation."""
    text = payload.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(canonical_text_bytes(payload)).hexdigest()


def canonical_sha256_text(text: str) -> str:
    return canonical_sha256_bytes(text.encode("utf-8"))


def canonical_file_sha256(path: Path) -> str:
    """Hash text canonically and retain byte-exact hashing for binary files."""
    payload = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        return canonical_sha256_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def markdown_sections(lines: list[str]) -> dict[str, dict[str, Any]]:
    """Return lightweight heading-to-heading section spans and hashes.

    This deliberately is not a Markdown AST.  The report workflow only needs
    a stable weak binding from a Rule's excerpt to the section that supplied
    it, so headings and line spans are sufficient and preserve compatibility
    with the project's many historical report formats.
    """
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line.strip())
        if match:
            title = re.sub(r"\s+", " ", match.group(2)).strip()
            if title:
                headings.append((index, title))
    sections: dict[str, dict[str, Any]] = {}
    for position, (start, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        key = title
        # Duplicate headings are valid in old reports.  Keep each span
        # addressable without pretending they are one semantic section.
        if key in sections:
            suffix = 2
            while f"{title}#{suffix}" in sections:
                suffix += 1
            key = f"{title}#{suffix}"
        text = "\n".join(lines[start:end]).strip()
        sections[key] = {
            "title": title,
            "line_start": start + 1,
            "line_end": end,
            "hash": canonical_sha256_text(text),
        }
    return sections


def source_metadata_for_excerpt(
    report_path: Path,
    lines: list[str],
    excerpt: dict[str, Any] | None,
    fallback_text: str,
) -> dict[str, Any]:
    """Build the minimal Rule-to-report source binding.

    ``source_hash`` hashes the exact captured evidence text.  The section hash
    hashes the containing Markdown heading span.  If an old structured field
    has no line excerpt, the full report hash is used as a conservative
    fallback: a later report edit must then be reviewed rather than silently
    treated as unaffected.
    """
    excerpt = excerpt if isinstance(excerpt, dict) else {}
    source_text = str(excerpt.get("text") or fallback_text or "").strip()
    start = excerpt.get("line_start")
    end = excerpt.get("line_end")
    try:
        start_number = int(start) if start is not None else None
        end_number = int(end) if end is not None else start_number
    except (TypeError, ValueError):
        start_number = end_number = None
    sections = markdown_sections(lines)
    containing: dict[str, Any] | None = None
    if start_number is not None:
        containing = next(
            (
                section
                for section in sections.values()
                if section["line_start"] <= start_number <= section["line_end"]
            ),
            None,
        )
    report_hash = canonical_file_sha256(report_path)
    return {
        "source_text": source_text,
        "source_hash": canonical_sha256_text(source_text),
        "source_section_hash": (containing or {}).get("hash") or report_hash,
        "source_line_start": start_number,
        "source_line_end": end_number,
    }
