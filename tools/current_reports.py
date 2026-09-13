#!/usr/bin/env python3
"""Canonical current-main-report registry (Git-managed source of truth).

The dashboard must not guess which historical Markdown report is a company's
current main report. This module owns ``data/investment-dashboard/current_reports.json``:
a ticker to immutable report path plus approved content SHA registry that the
production build treats as the only authority for current report selection.
Historical reports remain as archive assets and never compete for the current slot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FILENAME = "current_reports.json"
MIGRATION_FILENAME = "current_reports.migration.json"
CONTRACT_REVIEW_FILENAME = "contract_review_required.json"
SCHEMA_VERSION = 2
TRACKED_MANIFEST_SCHEMA_VERSION = 1


def tracked_paths(repo_root: Path, manifest: Path | None = None) -> set[str]:
    """Return formal Git assets from Git metadata or a release manifest.

    Production release directories deliberately do not contain ``.git``.  A
    manifest generated from the source checkout is therefore the only accepted
    substitute there; missing or malformed manifests fail closed.
    """
    if manifest is not None:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"tracked asset manifest is invalid: {manifest}: {error}") from error
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != TRACKED_MANIFEST_SCHEMA_VERSION
            or not isinstance(payload.get("tracked_paths"), list)
        ):
            raise ValueError(f"unsupported tracked asset manifest: {manifest}")
        return {str(item) for item in payload["tracked_paths"] if str(item).strip()}
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return {item.decode("utf-8") for item in completed.stdout.split(b"\0") if item}


def write_tracked_manifest(repo_root: Path, output: Path) -> dict[str, Any]:
    """Write a deterministic tracked-asset manifest from a real checkout."""
    paths = sorted(tracked_paths(repo_root))
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = {
        "schema_version": TRACKED_MANIFEST_SCHEMA_VERSION,
        "source_sha": completed.stdout.strip(),
        "tracked_paths": paths,
    }
    write_atomic(output, payload)
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path, *, strict: bool = True) -> dict[str, Any] | None:
    """Load and shape-check the canonical registry.

    ``strict`` only controls a missing file; malformed content always fails
    closed because production must never silently fall back to heuristics for a
    company that claims canonical ownership.
    """
    if not path.is_file():
        if strict:
            raise ValueError(f"canonical current reports file is missing: {path}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"canonical current reports file is invalid JSON: {path}: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported canonical current reports schema: {path}")
    companies = payload.get("companies")
    if not isinstance(companies, dict) or not companies:
        raise ValueError(f"canonical current reports must contain a non-empty companies mapping: {path}")
    return payload


def mappings(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return the ticker -> report path mapping from a loaded payload."""
    if not payload:
        return {}
    result: dict[str, str] = {}
    for raw_ticker, entry in payload.get("companies", {}).items():
        if not isinstance(entry, dict):
            continue
        report = str(entry.get("current_main_report") or "").strip()
        if raw_ticker and report:
            result[str(raw_ticker).upper()] = report
    return result


def legacy_allowlist(payload: dict[str, Any] | None) -> set[str]:
    """Return tickers still allowed to fall back to legacy ranking during migration."""
    if not payload:
        return set()
    entries = payload.get("legacy_tickers")
    if not isinstance(entries, list):
        return set()
    return {str(item).upper() for item in entries if str(item or "").strip()}


def quarantined_rule_tickers(payload: dict[str, Any] | None) -> set[str]:
    """Return stale rule identities explicitly excluded from production projection."""
    if not payload:
        return set()
    entries = payload.get("quarantined_rule_tickers")
    if not isinstance(entries, list):
        return set()
    return {str(item).upper() for item in entries if str(item or "").strip()}


def identity_rule_replacements(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return reviewed legacy-ticker -> corrected-ticker quarantine mappings."""
    if not payload or not isinstance(payload.get("identity_rule_replacements"), dict):
        return {}
    return {
        str(old).upper(): str(new).upper()
        for old, new in payload["identity_rule_replacements"].items()
        if str(old).strip() and str(new).strip()
    }


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write bytes through a same-directory temporary file and os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write a canonical payload (UTF-8 JSON) atomically."""
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_bytes_atomic(path, encoded)


def validate(
    payload: dict[str, Any],
    *,
    repo_root: Path,
    registry: list[dict[str, Any]],
    records_by_path: dict[str, dict[str, Any]],
    tracked: set[str] | None = None,
    require_tracked: bool = True,
) -> list[str]:
    """Return every validation error for a canonical payload (empty = valid)."""
    import build_investment_dashboard as dashboard  # lazy: avoids circular import

    errors: list[str] = []
    seen_paths: dict[str, str] = {}
    canonical_tickers = {str(raw).upper() for raw in payload.get("companies", {})}
    legacy_entries = payload.get("legacy_tickers")
    if "legacy_tickers" in payload and not isinstance(legacy_entries, list):
        errors.append("legacy_tickers must be a list")
        legacy_entries = []
    for raw_legacy in legacy_entries or []:
        legacy_ticker = str(raw_legacy).upper()
        if not legacy_ticker:
            errors.append("legacy_tickers must not contain empty values")
        elif legacy_ticker in canonical_tickers:
            errors.append(f"legacy ticker is also canonical: {legacy_ticker}")
    quarantine_entries = payload.get("quarantined_rule_tickers")
    if "quarantined_rule_tickers" in payload and not isinstance(quarantine_entries, list):
        errors.append("quarantined_rule_tickers must be a list")
        quarantine_entries = []
    for raw_quarantine in quarantine_entries or []:
        quarantined = str(raw_quarantine).upper()
        if quarantined in canonical_tickers:
            errors.append(f"quarantined rule ticker is also canonical: {quarantined}")
    replacements = identity_rule_replacements(payload)
    quarantined_rule_set = {
        str(item).upper() for item in quarantine_entries or [] if str(item).strip()
    }
    for old, new in replacements.items():
        if old not in quarantined_rule_set:
            errors.append(f"identity rule replacement source is not quarantined: {old}")
        if new not in canonical_tickers:
            errors.append(f"identity rule replacement target is not canonical: {new}")
    for raw_ticker, entry in payload.get("companies", {}).items():
        ticker = str(raw_ticker).upper()
        prefix = f"{ticker}: "
        if not isinstance(entry, dict):
            errors.append(prefix + "entry must be an object")
            continue
        company = str(entry.get("company") or "").strip()
        report = str(entry.get("current_main_report") or "").strip()
        approved_sha = str(entry.get("content_sha256") or "").strip().lower()
        if not company:
            errors.append(prefix + "company is required")
        if not report:
            errors.append(prefix + "current_main_report is required")
            continue
        if len(approved_sha) != 64 or any(character not in "0123456789abcdef" for character in approved_sha):
            errors.append(prefix + "content_sha256 must be a lowercase SHA-256 digest")
        report_path = repo_root / report
        if not report_path.is_file():
            errors.append(prefix + f"report file is missing: {report}")
            continue
        if require_tracked and tracked is not None and report not in tracked:
            errors.append(prefix + f"report is not Git tracked: {report}")
        if approved_sha and file_sha256(report_path) != approved_sha:
            errors.append(prefix + f"canonical content SHA mismatch: {report}")
        filename = Path(report).name.lower()
        if filename in {"readme.md", "moc.md"}:
            errors.append(prefix + f"index/README files cannot be canonical: {report}")
        if "checklist" in filename or "technical-analysis" in filename:
            errors.append(prefix + f"checklist/technical reports cannot be canonical: {report}")
        if any(part in dashboard.SKIPPED_PATH_PARTS for part in Path(report).parts):
            errors.append(prefix + f"canonical report is in a skipped/staging path: {report}")
        record = records_by_path.get(report)
        if record is None:
            errors.append(prefix + f"report is not a formal candidate asset: {report}")
            continue
        if dashboard.is_post_buy_tracking_report(record):
            errors.append(prefix + f"post-buy tracking report cannot be canonical: {report}")
        if dashboard.is_role_subreport_path(report):
            errors.append(prefix + f"role/topic sub-report cannot be canonical: {report}")
        record_ticker = str(record.get("ticker") or "").upper()
        if not record_ticker:
            errors.append(prefix + f"report has no parsed ticker: {report}")
        elif record_ticker != ticker:
            errors.append(prefix + f"ticker mismatch: registry={ticker} report={record_ticker}")
        record_company = dashboard.normalize_company_name(str(record.get("company") or ""))
        entry_company = dashboard.normalize_company_name(company)
        if record_company and entry_company and record_company != entry_company and not (
            record_company in entry_company or entry_company in record_company
        ):
            errors.append(prefix + f"company mismatch: registry={company} report={record.get('company')}")
        registry_entry = dashboard.registry_company(registry, company, ticker)
        if registry_entry is not None:
            tickers = {str(item).upper() for item in registry_entry.get("tickers", [])}
            blocked_tickers = {
                str(item).upper() for item in registry_entry.get("blocked_tickers", [])
            }
            if ticker in blocked_tickers:
                errors.append(
                    prefix
                    + "IDENTITY_REVIEW_REQUIRED: ticker is explicitly blocked for "
                    + str(registry_entry.get("canonical_name") or company)
                )
            if tickers and ticker not in tickers:
                errors.append(prefix + f"ticker is not in the company registry entry: {sorted(tickers)}")
            names = {dashboard.normalize_company_name(str(registry_entry.get("canonical_name") or ""))}
            names.update(
                dashboard.normalize_company_name(str(alias)) for alias in registry_entry.get("aliases", [])
            )
            names.discard("")
            if entry_company and names and entry_company not in names and not any(
                entry_company in name or name in entry_company for name in names
            ):
                errors.append(prefix + f"company identity does not match registry: {registry_entry.get('canonical_name')}")
        if report in seen_paths and seen_paths[report] != ticker:
            errors.append(prefix + f"report already points to another ticker: {seen_paths[report]} -> {report}")
        seen_paths[report] = ticker
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    manifest = subparsers.add_parser(
        "write-tracked-manifest",
        help="write a release manifest from a checkout that still has Git metadata",
    )
    manifest.add_argument("--repo-root", type=Path, default=ROOT)
    manifest.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "write-tracked-manifest":
        payload = write_tracked_manifest(arguments.repo_root.resolve(), arguments.output.resolve())
        print(json.dumps({"status": "ok", "tracked_count": len(payload["tracked_paths"])}, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
