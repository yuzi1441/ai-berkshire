#!/usr/bin/env python3
"""Resolve safe project-local destinations for newly generated reports.

This tool intentionally does not read, rewrite, or move report content. It only
chooses a destination directory and, when requested, creates that directory.
Keep the caller-provided report filename unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "report-routing" / "company_registry.json"
INBOX_DIRECTORY = Path("reports") / "_inbox" / "待归档"
COMPARISON_DIRECTORY = Path("reports") / "多公司对比"
REPORT_TYPES = ("company", "topic", "comparison", "unknown")


def normalize_text(value: str | None) -> str:
    """Normalize names and aliases without changing their display form."""
    return re.sub(r"\s+", "", (value or "").strip()).casefold()


def ticker_keys(ticker: str | None) -> set[str]:
    """Return equivalent lookup keys for common Chinese and Hong Kong tickers."""
    raw = (ticker or "").strip().upper().replace(" ", "")
    if not raw:
        return set()

    raw = raw.replace("SH.", "").replace("SZ.", "").replace("HK.", "")
    match = re.fullmatch(r"(?:([A-Z]+))?(\d+)(?:\.([A-Z]+))?", raw)
    if not match:
        return {raw}

    prefix, code, suffix = match.groups()
    keys = {raw, code}
    if suffix:
        keys.add(f"{code}.{suffix}")
    if prefix and prefix in {"SH", "SZ", "BJ", "HK"}:
        keys.add(f"{code}.{prefix}")
    if len(code) <= 5:
        hk_code = code.zfill(5)
        keys.update({hk_code, f"{hk_code}.HK"})
    return keys


def is_safe_segment(value: str | None) -> bool:
    """Accept a single, human-readable directory segment only."""
    if not value or value.strip() in {".", ".."}:
        return False
    return not any(character in value for character in ("/", "\\", "\x00"))


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Load and lightly validate the company routing registry."""
    with path.open(encoding="utf-8") as handle:
        registry = json.load(handle)
    if registry.get("schema_version") != 1 or not isinstance(registry.get("companies"), list):
        raise ValueError(f"Unsupported report routing registry: {path}")
    return registry


def find_company(registry: dict[str, Any], company: str | None, ticker: str | None) -> dict[str, Any] | None:
    """Resolve an exact ticker first, then a canonical name or configured alias."""
    requested_tickers = ticker_keys(ticker)
    if requested_tickers:
        for entry in registry["companies"]:
            entry_tickers = set()
            for candidate in entry.get("tickers", []):
                entry_tickers.update(ticker_keys(candidate))
            if requested_tickers & entry_tickers:
                return entry

    requested_name = normalize_text(company)
    if requested_name:
        for entry in registry["companies"]:
            names = [entry.get("canonical_name", ""), *entry.get("aliases", [])]
            if requested_name in {normalize_text(name) for name in names}:
                return entry
    return None


def build_result(
    *,
    status: str,
    directory: Path,
    reason: str,
    filename: str | None,
    company: str | None,
    topic: str | None,
    report_type: str,
    created: bool = False,
) -> dict[str, Any]:
    """Build a stable, JSON-serializable routing result."""
    basename = Path(filename).name if filename else None
    if filename and basename in {"", ".", ".."}:
        raise ValueError("A report filename must include a basename")

    result: dict[str, Any] = {
        "status": status,
        "report_type": report_type,
        "company": company or None,
        "topic": topic or None,
        "destination_dir": directory.as_posix(),
        "reason": reason,
        "created": created,
    }
    if basename:
        result["filename"] = basename
        result["destination_path"] = (directory / basename).as_posix()
    return result


def resolve_route(
    *,
    company: str | None = None,
    ticker: str | None = None,
    market: str | None = None,
    topic: str | None = None,
    report_type: str = "company",
    filename: str | None = None,
    repo_root: Path = ROOT,
    registry: dict[str, Any] | None = None,
    create: bool = False,
) -> dict[str, Any]:
    """Resolve a report destination without touching any report file."""
    if report_type not in REPORT_TYPES:
        raise ValueError(f"Unsupported report type: {report_type}")
    registry = registry if registry is not None else load_registry()
    target: Path
    status: str
    reason: str

    if report_type == "comparison":
        target = COMPARISON_DIRECTORY
        status = "resolved_comparison"
        reason = "comparison reports use the shared comparison directory"
    elif report_type == "topic":
        subject = (topic or company or "").strip()
        if is_safe_segment(subject):
            target = Path("reports") / subject
            status = "resolved_topic"
            reason = "topic name resolved directly"
        else:
            target = INBOX_DIRECTORY
            status = "routed_to_inbox"
            reason = "topic name is missing or unsafe"
    else:
        entry = find_company(registry, company, ticker)
        if entry:
            target = Path(entry["directory"])
            status = "resolved_registered_company"
            reason = f"matched registered company {entry['canonical_name']}"
        elif report_type == "company" and is_safe_segment((company or "").strip()):
            target = Path("reports") / company.strip()
            status = "resolved_new_company"
            reason = "company name is explicit; created or reused its company directory"
        else:
            target = INBOX_DIRECTORY
            status = "routed_to_inbox"
            detail = "no company or topic was provided" if not (company or topic or ticker) else "company or ticker could not be uniquely resolved"
            reason = detail

    destination = repo_root / target
    created = False
    if create and not destination.exists():
        destination.mkdir(parents=True, exist_ok=True)
        created = True

    return build_result(
        status=status,
        directory=target,
        reason=reason,
        filename=filename,
        company=company,
        topic=topic,
        report_type=report_type,
        created=created,
    )


def command_resolve(arguments: argparse.Namespace) -> int:
    """CLI wrapper for the resolver."""
    registry_path = Path(arguments.registry).resolve() if arguments.registry else DEFAULT_REGISTRY
    repo_root = Path(arguments.repo_root).resolve() if arguments.repo_root else ROOT
    try:
        result = resolve_route(
            company=arguments.company,
            ticker=arguments.ticker,
            market=arguments.market,
            topic=arguments.topic,
            report_type=arguments.report_type,
            filename=arguments.filename,
            repo_root=repo_root,
            registry=load_registry(registry_path),
            create=arguments.create,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if arguments.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"状态: {result['status']}")
        print(f"目录: {result['destination_dir']}")
        if "destination_path" in result:
            print(f"路径: {result['destination_path']}")
        print(f"原因: {result['reason']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve safe report destinations without modifying report content.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    resolve_parser = subparsers.add_parser("resolve", help="resolve a report destination")
    resolve_parser.add_argument("--company", help="canonical company name or known alias")
    resolve_parser.add_argument("--ticker", help="ticker, optionally with an exchange suffix")
    resolve_parser.add_argument("--market", help="display market context, such as A股 or 港股")
    resolve_parser.add_argument("--topic", help="topic name for topic reports")
    resolve_parser.add_argument("--report-type", choices=REPORT_TYPES, default="company")
    resolve_parser.add_argument("--filename", help="original report basename to place in the resolved directory")
    resolve_parser.add_argument("--create", action="store_true", help="create the destination directory only")
    resolve_parser.add_argument("--json", dest="as_json", action="store_true", help="emit JSON")
    resolve_parser.add_argument("--repo-root", help="repository root override for testing")
    resolve_parser.add_argument("--registry", help="registry path override for testing")
    resolve_parser.set_defaults(handler=command_resolve)
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
