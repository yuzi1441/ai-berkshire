#!/usr/bin/env python3
"""Validate and consume candidate semantic-review and current-fact records.

Both stores are deliberately non-production authorities.  They bind every
decision to the exact canonical report and semantic contract, and fail closed
when any binding, source, or validity window changes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


STORE_SCHEMA_VERSION = 1
RESOLUTION_STATUSES = {"VALID", "STALE", "REVIEW_REQUIRED", "UNKNOWN"}
REVIEW_STATUSES = {"PASS", "FAIL", "NEEDS_CLARIFICATION"}
PERSISTABLE_KINDS = {"METRIC_COMPARE", "QUALITATIVE", "FILING", "EVENT", "MANUAL_REVIEW", "UNKNOWN"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def node_semantic_fingerprint(node: dict[str, Any]) -> str:
    """Fingerprint every field that can change a leaf's decision meaning."""
    keys = (
        "node_id", "kind", "effect", "scope", "metric", "operator", "value", "unit",
        "price_min", "price_max", "currency", "price_role", "description", "evidence",
    )
    return canonical_sha256({key: node.get(key) for key in keys})


def evidence_source_fingerprints(evidence: list[dict[str, Any]], repo_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in evidence:
        source_path = str(item.get("source_path") or "")
        local = repo_root / source_path if source_path and "://" not in source_path else None
        if local is not None and local.is_file():
            result.append({"kind": "repo_file", "path": source_path, "content_sha256": sha256_file(local)})
        else:
            identity = source_path or str(item.get("record") or item.get("source") or "")
            result.append({
                "kind": "evidence_excerpt", "source_identity": identity,
                "content_sha256": canonical_sha256({
                    "source": item.get("source"), "identity": identity,
                    "date": item.get("date"), "value": item.get("value"),
                }),
            })
    return result


def _source_fingerprints_match(record: dict[str, Any], repo_root: Path) -> bool:
    evidence = record.get("evidence") if isinstance(record.get("evidence"), list) else []
    return record.get("source_fingerprints") == evidence_source_fingerprints(evidence, repo_root)


def resolution_effective_status(
    record: dict[str, Any], contract: dict[str, Any], contract_path: Path,
    node: dict[str, Any], repo_root: Path, as_of: date,
) -> tuple[str, str]:
    if record.get("resolution_status") not in RESOLUTION_STATUSES:
        return "STALE", "invalid_resolution_status"
    if record.get("resolution_status") in {"STALE", "REVIEW_REQUIRED"}:
        return str(record["resolution_status"]), "declared_not_reusable"
    if record.get("semantic_contract_sha256") != sha256_file(contract_path):
        return "STALE", "semantic_contract_sha_changed"
    if record.get("report_sha256") != contract.get("source", {}).get("report_sha256"):
        return "STALE", "report_sha_changed"
    if record.get("node_semantic_fingerprint") != node_semantic_fingerprint(node):
        return "STALE", "node_semantic_fingerprint_changed"
    if not _source_fingerprints_match(record, repo_root):
        return "REVIEW_REQUIRED", "source_fingerprint_changed"
    valid_until = record.get("valid_until")
    try:
        if valid_until and date.fromisoformat(str(valid_until)) < as_of:
            return "STALE", "valid_until_expired"
    except ValueError:
        return "STALE", "invalid_valid_until"
    review_after = record.get("review_after")
    try:
        if review_after and date.fromisoformat(str(review_after)) <= as_of:
            return "REVIEW_REQUIRED", "review_after_reached"
    except ValueError:
        return "REVIEW_REQUIRED", "invalid_review_after"
    for relative in record.get("filing_watch_paths", []):
        if (repo_root / str(relative)).exists():
            return "REVIEW_REQUIRED", "future_filing_became_available"
    return str(record["resolution_status"]), "bindings_current"


def validate_resolution_store(
    store: Any, contracts: dict[str, dict[str, Any]], contract_paths: dict[str, Path],
    nodes_by_ticker: dict[str, dict[str, dict[str, Any]]], repo_root: Path,
) -> list[str]:
    if not isinstance(store, dict) or store.get("schema_version") != STORE_SCHEMA_VERSION:
        return ["resolution store schema_version must be 1"]
    errors: list[str] = []
    if store.get("authority") != "candidate" or store.get("production_consumable") is not False:
        errors.append("resolution store must be candidate and production_consumable=false")
    records = store.get("resolutions")
    if not isinstance(records, list):
        return errors + ["resolutions must be a list"]
    seen: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        prefix = f"resolutions[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        ticker, node_id = str(record.get("ticker") or ""), str(record.get("node_id") or "")
        if (ticker, node_id) in seen:
            errors.append(f"{prefix} duplicate ticker/node_id")
        seen.add((ticker, node_id))
        contract = contracts.get(ticker)
        if contract is None:
            errors.append(f"{prefix} unknown ticker")
            continue
        node = nodes_by_ticker.get(ticker, {}).get(node_id)
        if node is None:
            errors.append(f"{prefix} node_id is not an evaluator leaf")
            continue
        kind = record.get("node_kind")
        if kind != node.get("kind") or kind not in PERSISTABLE_KINDS:
            errors.append(f"{prefix} node_kind mismatch or forbidden (prices are never cached)")
        required = (
            "company", "semantic_contract_sha256", "report_sha256", "node_semantic_fingerprint",
            "state", "resolution_status", "resolution_method", "evidence", "source_fingerprints",
            "source_date", "reporting_period", "created_at", "reviewed_at", "reason_code", "reviewed_by",
        )
        for field in required:
            if field not in record:
                errors.append(f"{prefix}.{field} is required")
        if record.get("company") != contract.get("company"):
            errors.append(f"{prefix}.company mismatch")
        if record.get("state") not in {True, False, "unknown"}:
            errors.append(f"{prefix}.state must be true, false, or unknown")
        if record.get("resolution_status") not in RESOLUTION_STATUSES:
            errors.append(f"{prefix}.resolution_status invalid")
        if record.get("reviewed_by") != "current_page_codex_semantic_review":
            errors.append(f"{prefix}.reviewed_by invalid")
        if not isinstance(record.get("source_fingerprints"), list):
            errors.append(f"{prefix}.source_fingerprints must be a list")
        if kind == "METRIC_COMPARE" and record.get("state") != "unknown" and "actual_value" not in record:
            errors.append(f"{prefix}.actual_value required for resolved metric")
        if record.get("state") in {True, False} and not record.get("evidence"):
            errors.append(f"{prefix}.evidence required for resolved state")
        # Version/source mismatches are lifecycle states, not malformed data.
        # resolution_effective_status() turns them into STALE/REVIEW_REQUIRED
        # and reusable_fact_packets() excludes them from evaluation.
        for field in ("semantic_contract_sha256", "report_sha256", "node_semantic_fingerprint"):
            value = record.get(field)
            if not isinstance(value, str) or len(value) != 64:
                errors.append(f"{prefix}.{field} must be a SHA-256 hex string")
    return errors


def reusable_fact_packets(
    store: dict[str, Any], contracts: dict[str, dict[str, Any]], contract_paths: dict[str, Path],
    nodes_by_ticker: dict[str, dict[str, dict[str, Any]]], repo_root: Path, as_of: date,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packets: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for record in store.get("resolutions", []):
        ticker, node_id = str(record["ticker"]), str(record["node_id"])
        node = nodes_by_ticker[ticker][node_id]
        status, reason = resolution_effective_status(
            record, contracts[ticker], contract_paths[ticker], node, repo_root, as_of
        )
        audit.append({"ticker": ticker, "node_id": node_id, "effective_status": status, "reason": reason})
        if status not in {"VALID", "UNKNOWN"}:
            continue
        packet = {
            "ticker": ticker, "company": record["company"], "node_id": node_id,
            "kind": record["node_kind"], "evidence": record.get("evidence", []),
            "evidence_date": record.get("source_date"), "period": record.get("reporting_period"),
            "required_period": record.get("required_period"), "valid_until": record.get("valid_until"),
            "reason_code": record.get("reason_code"), "reason": record.get("reason"),
        }
        if record["state"] == "unknown":
            packet["state"] = "unknown"
        elif record["node_kind"] == "METRIC_COMPARE":
            packet.update(actual_value=record["actual_value"], unit=record.get("unit"))
        else:
            packet["state"] = record["state"]
        packets.append({key: value for key, value in packet.items() if value is not None})
    return packets, audit


def validate_review_store(store: Any, contracts: dict[str, dict[str, Any]], contract_paths: dict[str, Path]) -> list[str]:
    if not isinstance(store, dict) or store.get("schema_version") != STORE_SCHEMA_VERSION:
        return ["semantic review store schema_version must be 1"]
    errors: list[str] = []
    if store.get("authority") != "candidate" or store.get("production_consumable") is not False:
        errors.append("semantic review store must be candidate and production_consumable=false")
    approvals = store.get("approvals")
    if not isinstance(approvals, list):
        return errors + ["approvals must be a list"]
    seen: set[str] = set()
    for index, approval in enumerate(approvals):
        prefix = f"approvals[{index}]"
        ticker = str(approval.get("ticker") or "")
        if ticker in seen:
            errors.append(f"{prefix} duplicate ticker")
        seen.add(ticker)
        contract = contracts.get(ticker)
        if contract is None:
            errors.append(f"{prefix} unknown ticker")
            continue
        if approval.get("company") != contract.get("company"):
            errors.append(f"{prefix}.company mismatch")
        if approval.get("review_status") not in REVIEW_STATUSES:
            errors.append(f"{prefix}.review_status invalid")
        if approval.get("reviewed_by") != "current_page_codex_semantic_review":
            errors.append(f"{prefix}.reviewed_by invalid")
        if not approval.get("reviewed_at") or not approval.get("review_findings") or not approval.get("evidence"):
            errors.append(f"{prefix} requires reviewed_at, review_findings, and evidence")
        binding_current = (
            approval.get("semantic_contract_sha256") == sha256_file(contract_paths[ticker])
            and approval.get("report_sha256") == contract.get("source", {}).get("report_sha256")
        )
        for field in ("semantic_contract_sha256", "report_sha256"):
            value = approval.get(field)
            if not isinstance(value, str) or len(value) != 64:
                errors.append(f"{prefix}.{field} must be a SHA-256 hex string")
        report_path = str(contract.get("source", {}).get("report_path") or "")
        report = contract_paths[ticker].parents[3] / report_path
        report_lines = report.read_text(encoding="utf-8").splitlines() if binding_current and report.is_file() else []
        for evidence_index, evidence in enumerate(approval.get("evidence", [])):
            evidence_prefix = f"{prefix}.evidence[{evidence_index}]"
            if not isinstance(evidence, dict) or evidence.get("report_path") != report_path:
                errors.append(f"{evidence_prefix} must reference the canonical report")
                continue
            if not binding_current:
                continue
            try:
                start, end = int(evidence["line_start"]), int(evidence["line_end"])
                excerpt = "\n".join(report_lines[start - 1:end])
                if str(evidence.get("quote") or "") not in excerpt:
                    errors.append(f"{evidence_prefix}.quote does not match report lines")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{evidence_prefix} requires valid line_start/line_end/quote")
    return errors


def approval_status(
    ticker: str, approvals: dict[str, dict[str, Any]], contract: dict[str, Any], contract_path: Path,
) -> str | None:
    approval = approvals.get(ticker)
    if not approval:
        return None
    if approval.get("semantic_contract_sha256") != sha256_file(contract_path):
        return None
    if approval.get("report_sha256") != contract.get("source", {}).get("report_sha256"):
        return None
    return str(approval.get("review_status"))
