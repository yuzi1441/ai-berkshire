#!/usr/bin/env python3
"""Durable WATCH thesis-drift scan coverage and freshness helpers.

``drift_states.json`` records material thesis changes.  This module owns the
separate scan checkpoint that records that a thesis was reviewed against a
known evidence state, including an ``unchanged`` or ``unknown`` conclusion.
The checkpoint is deliberately small and deterministic so a normal dashboard
build can derive freshness without rereading Markdown or using build times.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA_VERSION = 1
FINGERPRINT_VERSION = 2
SCAN_MODES = ("watch",)
SCAN_RESULTS = ("improved", "unchanged", "weakened", "unknown")
SCAN_STATUSES = ("current", "stale", "missing")
RELATIVE_PATH = Path("data/investment-dashboard/drift_scan_state.json")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_FINGERPRINT_RULE_DEFINITION_FIELDS = (
    "rule_id",
    "active",
    "rule_scope",
    "action",
    "type",
    "condition",
    "source",
    "source_report",
    "source_hash",
    "source_section",
    "source_section_hash",
)
_V1_FINGERPRINT_RULE_FIELDS = _FINGERPRINT_RULE_DEFINITION_FIELDS + ("status",)
_V1_FINGERPRINT_EVENT_FIELDS = (
    "event_id",
    "event_type",
    "state",
    "thesis_relevant",
    "recommended_action",
    "headline",
    "summary",
    "highest_source_tier",
    "evidence_count",
    "published_at",
)
_FINGERPRINT_EVENT_FIELDS = (
    "event_type",
    "state",
    "thesis_relevant",
    "headline",
    "summary",
    "highest_source_tier",
    "published_at",
)
_FINGERPRINT_EVIDENCE_FIELDS = (
    "title",
    "summary",
    "publisher",
    "url",
    "published_at",
    "source_tier",
    "verification_status",
    "direction",
    "impact",
    "relevance",
    "confidence",
)
_URL_TRACKING_PARAMS = {
    "_ga",
    "_gl",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def is_sha256(value: Any) -> bool:
    return bool(SHA256_RE.fullmatch(_text(value).lower()))


def _stable_dict(item: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: item.get(field) for field in fields if field in item}


def _normalize_url(value: Any) -> str | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw
    if not parsed.scheme or not parsed.netloc:
        return raw
    hostname = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = hostname
    if parsed.username or parsed.password:
        # Credentials are not useful evidence identity, but retain them rather
        # than silently changing an unusual URL.
        netloc = parsed.netloc.lower()
    elif port and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
        netloc = f"{hostname}:{port}"
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _URL_TRACKING_PARAMS and not key.lower().startswith("utm_")
    ]
    query.sort()
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path or "/",
            urlencode(query, doseq=True),
            "",
        )
    )


def _normalize_text_fields(item: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    result = _stable_dict(item, fields)
    for field in ("title", "summary", "publisher", "verification_status"):
        if field in result and result[field] is not None:
            result[field] = _text(result[field])
    if "url" in result:
        result["url"] = _normalize_url(result.get("url"))
    return result


def _stable_evidence_v1(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"text": _text(item)}
    return _stable_dict(item, _FINGERPRINT_EVIDENCE_FIELDS)


def stable_event_evidence_v1(event: dict[str, Any] | None) -> dict[str, Any]:
    """Return the pre-V2 event payload for explicit migration/audit only."""
    event = event if isinstance(event, dict) else {}
    events: list[dict[str, Any]] = []
    for item in event.get("events") or []:
        if not isinstance(item, dict):
            continue
        normalized = _stable_dict(item, _V1_FINGERPRINT_EVENT_FIELDS)
        evidence = [_stable_evidence_v1(entry) for entry in item.get("evidence") or []]
        normalized["evidence"] = sorted(evidence, key=_canonical)
        events.append(normalized)
    events.sort(key=_canonical)
    return {
        "state": event.get("state"),
        "thesis_relevant": bool(event.get("thesis_relevant")),
        "recommended_action": event.get("recommended_action"),
        "source_status": event.get("source_status"),
        "data_cutoff": event.get("data_cutoff"),
        "events": events,
    }


def _stable_material_event(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("thesis_relevant") is not True:
        return None
    normalized = _normalize_text_fields(item, _FINGERPRINT_EVENT_FIELDS)
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in item.get("evidence") or []:
        if not isinstance(entry, dict):
            continue
        stable = _normalize_text_fields(entry, _FINGERPRINT_EVIDENCE_FIELDS)
        key = _canonical(stable)
        if key in seen:
            continue
        seen.add(key)
        evidence.append(stable)
    normalized["evidence"] = sorted(evidence, key=_canonical)
    # event_id is intentionally excluded.  This key is derived from the
    # normalized material facts and evidence, not from retrieval metadata.
    normalized["semantic_key"] = hashlib.sha256(
        _canonical(normalized).encode("utf-8")
    ).hexdigest()[:24]
    return normalized


def stable_event_evidence(event: dict[str, Any] | None) -> dict[str, Any]:
    """Return only thesis-relevant event semantics under fingerprint V2."""
    event = event if isinstance(event, dict) else {}
    by_key: dict[str, dict[str, Any]] = {}
    for item in event.get("events") or []:
        if not isinstance(item, dict):
            continue
        normalized = _stable_material_event(item)
        if normalized is not None:
            by_key[normalized["semantic_key"]] = normalized
    return {"events": sorted(by_key.values(), key=_canonical)}


def _is_drift_relevant(rule: dict[str, Any]) -> bool:
    scope = _text(rule.get("rule_scope")).lower()
    action = _text(rule.get("action")).lower()
    if scope == "redline":
        return True
    return scope == "validation" and action in {"run_drift", "drop_or_recheck"}


def stable_drift_rules_v1(rules: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the pre-V2 drift Rule identity/status payload."""
    result = []
    for rule in rules:
        if not isinstance(rule, dict) or not _is_drift_relevant(rule):
            continue
        result.append(_stable_dict(rule, _V1_FINGERPRINT_RULE_FIELDS))
    return sorted(result, key=_canonical)


def _material_rule_status(rule: dict[str, Any]) -> bool:
    scope = _text(rule.get("rule_scope")).lower()
    action = _text(rule.get("action")).lower()
    if scope == "redline":
        return rule.get("status") == "triggered"
    return (
        scope == "validation"
        and action in {"run_drift", "drop_or_recheck"}
        and rule.get("status") == "triggered"
    )


def stable_drift_rules(rules: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return Rule definitions plus only material Drift trigger state."""
    result = []
    for rule in rules:
        if not isinstance(rule, dict) or not _is_drift_relevant(rule):
            continue
        normalized = _stable_dict(rule, _FINGERPRINT_RULE_DEFINITION_FIELDS)
        normalized["material_triggered"] = _material_rule_status(rule)
        result.append(normalized)
    return sorted(result, key=_canonical)


def _trigger_fingerprint_v1(
    ticker: str,
    baseline_report_sha256: str | None,
    rules: Iterable[dict[str, Any]],
    event: dict[str, Any] | None,
    *,
    research_evidence_sha256: str | None = None,
) -> str:
    semantic_state = {
        "version": 1,
        "ticker": _text(ticker).upper(),
        "baseline_report_sha256": baseline_report_sha256,
        "drift_relevant_rules": stable_drift_rules_v1(rules),
        "event_evidence": stable_event_evidence_v1(event),
        "research_evidence_sha256": research_evidence_sha256,
    }
    return hashlib.sha256(_canonical(semantic_state).encode("utf-8")).hexdigest()


def trigger_fingerprint_v1(
    ticker: str,
    baseline_report_sha256: str | None,
    rules: Iterable[dict[str, Any]],
    event: dict[str, Any] | None,
    *,
    research_evidence_sha256: str | None = None,
) -> str:
    """Calculate the legacy V1 fingerprint for explicit migration audits."""
    return _trigger_fingerprint_v1(
        ticker,
        baseline_report_sha256,
        rules,
        event,
        research_evidence_sha256=research_evidence_sha256,
    )


def trigger_fingerprint(
    ticker: str,
    baseline_report_sha256: str | None,
    rules: Iterable[dict[str, Any]],
    event: dict[str, Any] | None,
    *,
    research_evidence_sha256: str | None = None,
) -> str:
    """Hash material scan inputs under the explicit V2 contract."""
    semantic_state = {
        "version": FINGERPRINT_VERSION,
        "ticker": _text(ticker).upper(),
        "baseline_report_sha256": baseline_report_sha256,
        "drift_relevant_rules": stable_drift_rules(rules),
        "event_evidence": stable_event_evidence(event),
    }
    return hashlib.sha256(_canonical(semantic_state).encode("utf-8")).hexdigest()


def checkpoint_status(
    checkpoint: dict[str, Any] | None,
    *,
    mode: str,
    baseline_report_sha256: str | None,
    current_trigger_fingerprint: str,
) -> str:
    if not isinstance(checkpoint, dict):
        return "missing"
    if _text(checkpoint.get("mode")).lower() != _text(mode).lower():
        return "stale"
    if checkpoint.get("trigger_fingerprint_version") != FINGERPRINT_VERSION:
        return "stale"
    if checkpoint.get("baseline_report_sha256") != baseline_report_sha256:
        return "stale"
    if checkpoint.get("trigger_fingerprint") != current_trigger_fingerprint:
        return "stale"
    return "current"


def project_checkpoint(
    checkpoint: dict[str, Any] | None,
    *,
    mode: str,
    baseline_report_sha256: str | None,
    current_trigger_fingerprint: str,
) -> dict[str, Any]:
    """Return a UI/read-model projection with derived current/stale status."""
    status = checkpoint_status(
        checkpoint,
        mode=mode,
        baseline_report_sha256=baseline_report_sha256,
        current_trigger_fingerprint=current_trigger_fingerprint,
    )
    if status == "missing":
        return {
            "status": "missing",
            "result": None,
            "trigger_fingerprint_version": FINGERPRINT_VERSION,
            "checked_at": None,
            "baseline_report_sha256": baseline_report_sha256,
            "trigger_fingerprint": current_trigger_fingerprint,
            "batch_id": None,
            "source": None,
        }
    result = dict(checkpoint)
    result["status"] = status
    result["current_trigger_fingerprint"] = current_trigger_fingerprint
    return result


def _valid_checked_at(value: Any) -> bool:
    raw = _text(value)
    if not raw:
        return False
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return True
    except ValueError:
        try:
            date.fromisoformat(raw)
            return True
        except ValueError:
            return False


def validate_payload(payload: Any, *, repo_root: Path | None = None) -> list[str]:
    """Validate persisted scan checkpoints; missing file is handled by caller."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["drift_scan_state must be an object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("drift_scan_state schema_version")
    if payload.get("trigger_fingerprint_version") != FINGERPRINT_VERSION:
        errors.append("drift_scan_state trigger_fingerprint_version")
    companies = payload.get("companies")
    if not isinstance(companies, dict):
        return errors + ["drift_scan_state companies"]
    for key, record in companies.items():
        ticker = _text(key).upper()
        if not isinstance(record, dict):
            errors.append(f"drift_scan record not object: {ticker}")
            continue
        if _text(record.get("ticker")).upper() != ticker:
            errors.append(f"drift_scan ticker mismatch: {ticker}")
        if _text(record.get("mode")).lower() not in SCAN_MODES:
            errors.append(f"drift_scan mode: {ticker}")
        if record.get("trigger_fingerprint_version") != FINGERPRINT_VERSION:
            errors.append(f"drift_scan trigger_fingerprint_version: {ticker}")
        if _text(record.get("result")).lower() not in SCAN_RESULTS:
            errors.append(f"drift_scan result: {ticker}")
        if not _valid_checked_at(record.get("checked_at")):
            errors.append(f"drift_scan checked_at: {ticker}")
        report = _text(record.get("baseline_report"))
        if not report:
            errors.append(f"drift_scan baseline_report: {ticker}")
        report_sha = _text(record.get("baseline_report_sha256")).lower()
        if not is_sha256(report_sha):
            errors.append(f"drift_scan baseline_report_sha256: {ticker}")
        fingerprint = _text(record.get("trigger_fingerprint")).lower()
        if not is_sha256(fingerprint):
            errors.append(f"drift_scan trigger_fingerprint: {ticker}")
        research_sha = record.get("research_evidence_sha256")
        if research_sha is not None and not is_sha256(research_sha):
            errors.append(f"drift_scan research_evidence_sha256: {ticker}")
        if repo_root is not None and report:
            root = repo_root.resolve()
            report_path = (root / report).resolve()
            try:
                report_path.relative_to(root)
            except ValueError:
                errors.append(f"drift_scan baseline outside repo: {ticker}")
                continue
            if not report_path.is_file():
                errors.append(f"drift_scan baseline missing: {ticker}")
            # A report hash differing from the stored baseline is a valid
            # freshness transition (the checkpoint becomes ``stale``), not a
            # malformed checkpoint.  The importer verifies the hash at write
            # time; the builder must be able to read an older baseline in
            # order to derive that stale state.
    return errors


def load(path: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    """Load an optional checkpoint; a present malformed file fails closed."""
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "companies": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid drift_scan_state: {path}: {error}") from error
    errors = validate_payload(payload, repo_root=repo_root)
    if errors:
        raise ValueError("Invalid drift_scan_state: " + "; ".join(errors))
    return payload
