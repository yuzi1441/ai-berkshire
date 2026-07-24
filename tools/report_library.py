#!/usr/bin/env python3
"""Plan and apply an auditable, conflict-safe cleanup of legacy root reports.

Only Markdown files immediately inside ``reports/`` are in scope. The tool never
changes report bytes: it moves each file to an explicitly reviewed destination,
or to the shared inbox when no mapping exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIRECTORY = ROOT / "reports"
DEFAULT_MAPPING_PATH = ROOT / "data" / "report-routing" / "root_report_migration.json"
INBOX_DIRECTORY = Path("reports") / "_inbox" / "待归档"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without decoding its content."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_mappings(path: Path) -> dict[str, str]:
    """Load and validate the reviewed legacy report destination mapping."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    mappings = payload.get("mappings")
    if payload.get("schema_version") != 1 or not isinstance(mappings, dict):
        raise ValueError(f"Unsupported migration mapping file: {path}")

    for filename, destination in mappings.items():
        if Path(filename).name != filename or not isinstance(destination, str):
            raise ValueError(f"Invalid migration mapping: {filename!r}")
        target = Path(destination)
        if not target.parts or target.parts[0] != "reports" or ".." in target.parts:
            raise ValueError(f"Unsafe migration destination: {destination!r}")
    return mappings


def suffixed_path(destination: Path, label: str) -> Path:
    """Return a non-existing conflict-preserving destination path."""
    candidate = destination.with_name(f"{destination.stem}.{label}{destination.suffix}")
    sequence = 2
    while candidate.exists():
        candidate = destination.with_name(
            f"{destination.stem}.{label}-{sequence}{destination.suffix}"
        )
        sequence += 1
    return candidate


def build_plan(
    repo_root: Path = ROOT,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Build an explicit migration plan without changing report files.

    Args:
        repo_root: Repository root containing ``reports/``.
        mapping_path: JSON map with reviewed file destinations.
        timestamp: Optional stable timestamp for tests and audit filenames.

    Returns:
        JSON-serializable plan with one operation for every root Markdown file.
    """
    mappings = load_mappings(mapping_path)
    reports_directory = repo_root / "reports"
    when = timestamp or datetime.now().astimezone()
    label = f"from-root-{when:%Y%m%d}"
    operations: list[dict[str, Any]] = []

    for source in sorted(reports_directory.glob("*.md"), key=lambda item: item.name.casefold()):
        mapped_directory = mappings.get(source.name)
        destination_directory = Path(mapped_directory) if mapped_directory else INBOX_DIRECTORY
        destination = repo_root / destination_directory / source.name
        reason = "reviewed explicit mapping" if mapped_directory else "no reviewed mapping; routed to inbox"
        conflict = "none"

        if destination.exists():
            if sha256_file(source) == sha256_file(destination):
                conflict = "same_content_duplicate"
                destination = suffixed_path(destination, f"duplicate-{label}")
            else:
                conflict = "different_content_conflict"
                destination = suffixed_path(destination, f"conflict-{label}")

        operations.append(
            {
                "action": "move",
                "source": source.relative_to(repo_root).as_posix(),
                "destination": destination.relative_to(repo_root).as_posix(),
                "source_sha256": sha256_file(source),
                "reason": reason,
                "conflict": conflict,
            }
        )

    return {
        "schema_version": 1,
        "generated_at": when.isoformat(timespec="seconds"),
        "mapping_file": mapping_path.relative_to(ROOT).as_posix()
        if mapping_path.is_relative_to(ROOT)
        else str(mapping_path),
        "operation_count": len(operations),
        "operations": operations,
    }


def validate_operation(repo_root: Path, operation: dict[str, Any]) -> tuple[Path, Path]:
    """Validate one planned move before making any filesystem change."""
    source = repo_root / operation["source"]
    destination = repo_root / operation["destination"]
    reports_root = (repo_root / "reports").resolve()
    if source.parent.resolve() != reports_root:
        raise ValueError(f"Source is not a root report: {source}")
    if reports_root not in destination.resolve().parents:
        raise ValueError(f"Destination is outside reports/: {destination}")
    if not source.is_file():
        raise FileNotFoundError(f"Planned source no longer exists: {source}")
    if destination.exists():
        raise FileExistsError(f"Planned destination now exists: {destination}")
    if sha256_file(source) != operation["source_sha256"]:
        raise ValueError(f"Source changed after planning: {source}")
    return source, destination


def apply_plan(repo_root: Path, plan: dict[str, Any], log_path: Path) -> dict[str, Any]:
    """Apply a previously generated plan and write a durable migration log."""
    if plan.get("schema_version") != 1 or not isinstance(plan.get("operations"), list):
        raise ValueError("Unsupported migration plan")

    validated = [validate_operation(repo_root, operation) for operation in plan["operations"]]
    applied: list[dict[str, Any]] = []
    for operation, (source, destination) in zip(plan["operations"], validated, strict=True):
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        applied.append({**operation, "status": "moved"})

    result = {
        "schema_version": 1,
        "applied_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "plan_generated_at": plan.get("generated_at"),
        "operation_count": len(applied),
        "operations": applied,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def write_json(payload: dict[str, Any], output_path: Path | None) -> None:
    """Write JSON to a file or standard output using a stable encoding."""
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def write_ledger(log: dict[str, Any], output_path: Path) -> None:
    """Create an Obsidian-readable classification ledger from a migration log."""
    operations = log.get("operations")
    if log.get("schema_version") != 1 or not isinstance(operations, list):
        raise ValueError("Unsupported migration log")
    lines = [
        "---",
        'title: "报告分类台账"',
        "type: generated-index",
        f"generated_at: {log.get('applied_at', 'unknown')}",
        "---",
        "",
        "# 报告分类台账",
        "",
        "> 本台账由迁移日志生成。文件正文未被改写；同名冲突文件以来源后缀保留。",
        "",
        "| 原位置 | 当前归档位置 | 分类依据 | 冲突处理 |",
        "|---|---|---|---|",
    ]
    for operation in operations:
        source = str(operation.get("source", "-")).replace("|", "\\|")
        destination = str(operation.get("destination", "-")).replace("|", "\\|")
        reason = str(operation.get("reason", "-")).replace("|", "\\|")
        conflict = str(operation.get("conflict", "none")).replace("_", " ")
        lines.append(f"| `{source}` | `{destination}` | {reason} | {conflict} |")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="create a non-mutating migration plan")
    plan_parser.add_argument("--output", type=Path, help="write the plan to this JSON file")

    apply_parser = subparsers.add_parser("apply", help="apply a previously reviewed migration plan")
    apply_parser.add_argument("--plan", required=True, type=Path, help="migration plan generated by plan")
    apply_parser.add_argument("--log", type=Path, help="destination audit log path")

    ledger_parser = subparsers.add_parser("ledger", help="write an Obsidian classification ledger from a migration log")
    ledger_parser.add_argument("--log", required=True, type=Path, help="migration audit log")
    ledger_parser.add_argument("--output", type=Path, help="Obsidian ledger destination")
    return parser


def main() -> int:
    """Run the report library migration CLI."""
    arguments = build_parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    mapping_path = arguments.mapping.resolve()
    try:
        if arguments.command == "plan":
            plan = build_plan(repo_root, mapping_path)
            output = arguments.output.resolve() if arguments.output else None
            write_json(plan, output)
            return 0

        if arguments.command == "ledger":
            log = json.loads(arguments.log.read_text(encoding="utf-8"))
            output = arguments.output or (repo_root / "reports" / "00-index" / "报告分类台账.md")
            write_ledger(log, output.resolve())
            print(f"Wrote report classification ledger: {output}")
            return 0

        plan = json.loads(arguments.plan.read_text(encoding="utf-8"))
        log_path = arguments.log or (
            repo_root / "logs" / "report-library" / f"migration-{datetime.now():%Y%m%d}.json"
        )
        result = apply_plan(repo_root, plan, log_path.resolve())
        print(f"Moved {result['operation_count']} reports; audit log: {log_path}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
