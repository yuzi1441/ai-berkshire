"""Stable source fingerprints shared by report and dashboard workflows.

Git checkouts may expose the same text with LF on macOS and CRLF on Windows.
Review rules are bound to report content, not to the checkout's newline style,
so text fingerprints normalise BOMs and line endings before hashing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


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
