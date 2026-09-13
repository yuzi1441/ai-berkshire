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
TRACKED_MANIFEST_FILENAME = ".tracked-assets.json"
BOOTSTRAP_MANIFEST_KIND = "repository_bootstrap"
RELEASE_MANIFEST_KIND = "release_snapshot"


def _require_exact_git_root(repo_root: Path) -> None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(
            f"TRACKED_ASSET_PROOF_UNAVAILABLE: Git metadata is unavailable under {repo_root}"
        ) from error
    if Path(completed.stdout.strip()).resolve() != repo_root.resolve():
        raise ValueError(
            f"TRACKED_ASSET_PROOF_UNAVAILABLE: Git metadata does not belong to {repo_root}"
        )


def _tracked_paths_digest(paths: list[str]) -> str:
    """Return the deterministic digest used to make path-list tampering visible."""
    return hashlib.sha256("\0".join(paths).encode("utf-8")).hexdigest()


def _git_index_identity(
    repo_root: Path,
    manifest_relative: str,
    *,
    worktree_overrides: set[str] | None = None,
) -> str:
    """Hash staged entries, optionally projecting verified tracked worktree writes."""
    _require_exact_git_root(repo_root)
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"Git index identity is unavailable under {repo_root}") from error
    entries: dict[str, tuple[bytes, bytes]] = {}
    for entry in completed.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            _mode, _object_id, stage = metadata.split(b" ", 2)
        except ValueError as error:
            raise ValueError("Git index contains an unreadable entry") from error
        path = raw_path.decode("utf-8")
        if stage != b"0":
            raise ValueError(f"Git index contains an unresolved entry: {path}")
        if path != manifest_relative:
            entries[path] = (_mode, _object_id)
    for path in sorted(worktree_overrides or set()):
        if path == manifest_relative or path not in entries:
            continue
        candidate = repo_root / path
        if not candidate.is_file():
            entries.pop(path, None)
            continue
        completed = subprocess.run(
            ["git", "hash-object", "--", path],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        entries[path] = (entries[path][0], completed.stdout.strip().encode("ascii"))
    encoded = [
        mode + b" " + object_id + b" 0\t" + path.encode("utf-8")
        for path, (mode, object_id) in entries.items()
    ]
    return hashlib.sha256(b"\0".join(sorted(encoded))).hexdigest()


def _load_tracked_manifest(path: Path, *, require_bootstrap: bool = False) -> set[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"tracked asset manifest is invalid: {path}: {error}") from error
    raw_paths = payload.get("tracked_paths") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != TRACKED_MANIFEST_SCHEMA_VERSION
        or not isinstance(raw_paths, list)
    ):
        raise ValueError(f"unsupported tracked asset manifest: {path}")
    if require_bootstrap and payload.get("manifest_kind") != BOOTSTRAP_MANIFEST_KIND:
        raise ValueError(f"auto-discovered tracked asset manifest is not a bootstrap manifest: {path}")
    paths: list[str] = []
    for item in raw_paths:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"tracked asset manifest contains an invalid path: {path}")
        normalized = Path(item)
        if normalized.is_absolute() or ".." in normalized.parts or normalized.as_posix() != item:
            raise ValueError(f"tracked asset manifest contains an unsafe path: {item}")
        paths.append(item)
    if len(paths) != len(set(paths)) or paths != sorted(paths):
        raise ValueError(f"tracked asset manifest paths must be unique and sorted: {path}")
    expected_digest = payload.get("tracked_paths_sha256")
    if expected_digest is not None and expected_digest != _tracked_paths_digest(paths):
        raise ValueError(f"tracked asset manifest digest mismatch: {path}")
    if require_bootstrap and not expected_digest:
        raise ValueError(f"bootstrap tracked asset manifest has no digest: {path}")
    if require_bootstrap:
        binding = payload.get("source_binding")
        if (
            not isinstance(binding, dict)
            or binding.get("kind") != "git_index_without_manifest"
            or not isinstance(binding.get("sha256"), str)
            or len(binding["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in binding["sha256"])
        ):
            raise ValueError(f"bootstrap tracked asset manifest has invalid source binding: {path}")
    return set(paths)


def _git_tracked_paths(repo_root: Path) -> set[str]:
    _require_exact_git_root(repo_root)
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(
            f"tracked asset proof is unavailable: no valid manifest or Git index under {repo_root}"
        ) from error
    return {item.decode("utf-8") for item in completed.stdout.split(b"\0") if item}


def tracked_paths(repo_root: Path, manifest: Path | None = None) -> set[str]:
    """Return formal Git assets from Git metadata or a release manifest.

    Production release directories deliberately do not contain ``.git``.  A
    manifest generated from the source checkout is therefore the only accepted
    substitute there; missing or malformed manifests fail closed.
    """
    if manifest is not None:
        return _load_tracked_manifest(manifest)
    # A real checkout always uses its live Git index. Auto-discovery is only
    # for the no-Git staging tree created by an installed release publisher.
    if (repo_root / ".git").exists():
        return _git_tracked_paths(repo_root)
    bootstrap = repo_root / TRACKED_MANIFEST_FILENAME
    if bootstrap.is_file():
        return _load_tracked_manifest(bootstrap, require_bootstrap=True)
    return _git_tracked_paths(repo_root)


def write_tracked_manifest(repo_root: Path, output: Path) -> dict[str, Any]:
    """Write a deterministic tracked-asset manifest from a real checkout."""
    paths = sorted(_git_tracked_paths(repo_root))
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = {
        "schema_version": TRACKED_MANIFEST_SCHEMA_VERSION,
        "manifest_kind": RELEASE_MANIFEST_KIND,
        "source_sha": completed.stdout.strip(),
        "tracked_paths": paths,
        "tracked_paths_sha256": _tracked_paths_digest(paths),
    }
    write_atomic(output, payload)
    return payload


def bootstrap_manifest_payload(
    repo_root: Path,
    output: Path,
    *,
    worktree_overrides: set[str] | None = None,
) -> dict[str, Any]:
    """Generate the deterministic bootstrap payload from the live Git index."""
    paths = _git_tracked_paths(repo_root)
    try:
        output_relative = output.relative_to(repo_root).as_posix()
    except ValueError as error:
        raise ValueError("bootstrap manifest must be inside the repository root") from error
    paths.add(output_relative)
    ordered = sorted(paths)
    return {
        "schema_version": TRACKED_MANIFEST_SCHEMA_VERSION,
        "manifest_kind": BOOTSTRAP_MANIFEST_KIND,
        "tracked_paths": ordered,
        "tracked_paths_sha256": _tracked_paths_digest(ordered),
        "source_binding": {
            "kind": "git_index_without_manifest",
            "sha256": _git_index_identity(
                repo_root,
                output_relative,
                worktree_overrides=worktree_overrides,
            ),
        },
    }


def write_bootstrap_manifest(
    repo_root: Path,
    output: Path,
    *,
    worktree_overrides: set[str] | None = None,
) -> dict[str, Any]:
    """Write the source-controlled proof consumed by an old release publisher."""
    payload = bootstrap_manifest_payload(
        repo_root, output, worktree_overrides=worktree_overrides
    )
    write_atomic(output, payload)
    return payload


def verify_bootstrap_manifest(
    repo_root: Path,
    manifest: Path,
    *,
    worktree_overrides: set[str] | None = None,
) -> int:
    """Regenerate in memory and fail unless the committed proof is current."""
    manifest_paths = _load_tracked_manifest(manifest, require_bootstrap=True)
    expected_payload = bootstrap_manifest_payload(
        repo_root, manifest, worktree_overrides=worktree_overrides
    )
    expected = set(expected_payload["tracked_paths"])
    if manifest_paths != expected:
        missing = sorted(expected - manifest_paths)
        extra = sorted(manifest_paths - expected)
        raise ValueError(
            "bootstrap tracked asset manifest does not match Git index"
            f"; missing={missing[:10]}; extra={extra[:10]}; regenerate with: "
            "python3 tools/current_reports.py write-bootstrap-manifest --repo-root ."
        )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload != expected_payload:
        raise ValueError(
            "bootstrap tracked asset manifest differs from deterministic regeneration; regenerate with: "
            "python3 tools/current_reports.py write-bootstrap-manifest --repo-root ."
        )
    return len(manifest_paths)


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
    bootstrap = subparsers.add_parser(
        "write-bootstrap-manifest",
        help="write the source-controlled manifest used by old release publishers",
    )
    bootstrap.add_argument("--repo-root", type=Path, default=ROOT)
    bootstrap.add_argument("--output", type=Path, default=Path(TRACKED_MANIFEST_FILENAME))
    verify = subparsers.add_parser(
        "verify-bootstrap-manifest",
        help="verify that the bootstrap manifest exactly matches the Git index",
    )
    verify.add_argument("--repo-root", type=Path, default=ROOT)
    verify.add_argument("--manifest", type=Path, default=Path(TRACKED_MANIFEST_FILENAME))
    arguments = parser.parse_args()
    if arguments.command == "write-tracked-manifest":
        payload = write_tracked_manifest(arguments.repo_root.resolve(), arguments.output.resolve())
        print(json.dumps({"status": "ok", "tracked_count": len(payload["tracked_paths"])}, ensure_ascii=False))
        return 0
    if arguments.command == "write-bootstrap-manifest":
        root = arguments.repo_root.resolve()
        output = arguments.output if arguments.output.is_absolute() else root / arguments.output
        payload = write_bootstrap_manifest(root, output.resolve())
        print(json.dumps({"status": "ok", "tracked_count": len(payload["tracked_paths"])}, ensure_ascii=False))
        return 0
    if arguments.command == "verify-bootstrap-manifest":
        root = arguments.repo_root.resolve()
        manifest_path = arguments.manifest if arguments.manifest.is_absolute() else root / arguments.manifest
        count = verify_bootstrap_manifest(root, manifest_path.resolve())
        print(json.dumps({"status": "ok", "tracked_count": count}, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
