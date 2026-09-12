#!/usr/bin/env python3
"""Manage Git-authoritative, holding-cycle-bound research review results.

Execution facts (position state, cost and weight) remain in runtime
``post_buy_tracking.json``.  This file stores only publishable research
results and applies them when all immutable bindings still match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from source_hash import canonical_file_sha256


ROOT = Path(__file__).resolve().parents[1]
RELATIVE_PATH = Path("data/investment-dashboard/holding_research_reviews.json")
SCHEMA_VERSION = 1
THESIS_STATUSES = frozenset({"not_established", "healthy", "borderline", "damaged", "broken"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def empty_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "authority": "git",
        "description": "Publishable holding research only; execution facts remain runtime-authoritative.",
        "reviews": {},
    }


def load(path: Path, *, strict: bool = True) -> dict[str, Any]:
    if not path.is_file():
        return empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        if strict:
            raise ValueError(f"invalid holding research reviews: {path}: {error}") from error
        return empty_payload()
    errors = validate_payload(payload)
    if errors and strict:
        raise ValueError("invalid holding research reviews: " + "; ".join(errors))
    return payload if isinstance(payload, dict) else empty_payload()


def _valid_date(value: Any) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def validate_payload(
    payload: Any, *, repo_root: Path | None = None, allow_migration: bool = True
) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    if payload.get("authority") != "git":
        errors.append("authority must be git")
    reviews = payload.get("reviews")
    if not isinstance(reviews, dict):
        return errors + ["reviews must be an object"]
    root = repo_root.resolve() if repo_root else None
    for key, review in reviews.items():
        prefix = f"reviews.{key}"
        if not isinstance(review, dict):
            errors.append(f"{prefix} must be an object")
            continue
        ticker = str(review.get("ticker") or "").upper()
        position_id = str(review.get("position_id") or "")
        if key != position_id or not ticker or not position_id.startswith(f"{ticker}:"):
            errors.append(f"{prefix} identity mismatch")
        for field in ("original_buy_thesis_sha256", "report_sha256"):
            if not SHA256_RE.fullmatch(str(review.get(field) or "")):
                errors.append(f"{prefix}.{field}")
        if review.get("thesis_status") not in THESIS_STATUSES:
            errors.append(f"{prefix}.thesis_status")
        score = review.get("health_score")
        if score is not None and (not isinstance(score, (int, float)) or isinstance(score, bool) or not 1 <= score <= 10):
            errors.append(f"{prefix}.health_score")
        if not allow_migration and (score is None or not str(review.get("review_action") or "").strip()):
            errors.append(f"{prefix}.health_score/review_action required for new review")
        for field in ("reviewed_at", "next_review_date"):
            if not _valid_date(review.get(field)):
                errors.append(f"{prefix}.{field}")
        if all(_valid_date(review.get(field)) for field in ("reviewed_at", "next_review_date")):
            if review["next_review_date"] <= review["reviewed_at"]:
                errors.append(f"{prefix}.next_review_date must follow reviewed_at")
        for field in ("metrics", "evidence"):
            if not isinstance(review.get(field, []), list):
                errors.append(f"{prefix}.{field}")
        migrated = (
            allow_migration
            and review.get("provenance") == "migration_from_post_buy_tracking"
            and review.get("migration_preserves_original_review_date") is True
        )
        if not migrated and not review.get("evidence"):
            errors.append(f"{prefix}.evidence must contain stable references")
        for item in review.get("evidence", []) if isinstance(review.get("evidence"), list) else []:
            if not isinstance(item, dict):
                errors.append(f"{prefix}.evidence item must be an object")
                continue
            if not item.get("source_identity") or not SHA256_RE.fullmatch(str(item.get("content_sha256") or "")):
                errors.append(f"{prefix}.evidence identity/hash")
            if not _valid_date(item.get("date")):
                errors.append(f"{prefix}.evidence date")
            elif _valid_date(review.get("reviewed_at")) and item["date"] > review["reviewed_at"]:
                errors.append(f"{prefix}.evidence is newer than review")
        report_path = str(review.get("report_path") or "")
        if not report_path:
            errors.append(f"{prefix}.report_path")
        elif root is not None:
            candidate = (root / report_path).resolve()
            if root not in candidate.parents or not candidate.is_file():
                errors.append(f"{prefix}.report_path missing")
            elif canonical_file_sha256(candidate) != review.get("report_sha256"):
                errors.append(f"{prefix}.report_sha256 mismatch")
    return errors


def binding_status(
    review: dict[str, Any] | None,
    position: dict[str, Any],
    original_buy_theses: dict[str, Any],
    repo_root: Path,
) -> tuple[str, list[str]]:
    if not isinstance(review, dict):
        return "unreviewed", ["no_git_research_review"]
    reasons: list[str] = []
    ticker = str(position.get("ticker") or "").upper()
    position_id = str(position.get("position_id") or "")
    active_id = str((original_buy_theses.get("active_position_ids") or {}).get(ticker) or "")
    cycle = (original_buy_theses.get("cycles") or {}).get(position_id)
    if review.get("ticker") != ticker:
        reasons.append("ticker_mismatch")
    if review.get("position_id") != position_id:
        reasons.append("position_id_mismatch")
    if active_id != position_id:
        reasons.append("active_position_mismatch")
    if not isinstance(cycle, dict):
        reasons.append("original_buy_thesis_missing")
    elif review.get("original_buy_thesis_sha256") != cycle.get("source_hash"):
        reasons.append("original_buy_thesis_sha256_mismatch")
    raw_path = str(review.get("report_path") or "")
    report = (repo_root.resolve() / raw_path).resolve()
    if repo_root.resolve() not in report.parents or not report.is_file():
        reasons.append("research_report_missing")
    elif canonical_file_sha256(report) != review.get("report_sha256"):
        reasons.append("research_report_sha256_mismatch")
    return ("matched", []) if not reasons else ("binding_mismatch", reasons)


def apply_review(
    projection: dict[str, Any],
    *,
    review: dict[str, Any] | None,
    position: dict[str, Any],
    original_buy_theses: dict[str, Any],
    repo_root: Path,
    allow_legacy: bool = False,
) -> dict[str, Any]:
    status, reasons = binding_status(review, position, original_buy_theses, repo_root)
    projection["research_binding_status"] = status
    projection["research_binding_reasons"] = reasons
    # Refresh report integrity on every projection, including builds without check.
    projection["news_pulse_events"] = project_news_events(position, repo_root)
    if status == "matched" and review is not None:
        projection.update({
            "thesis_report_path": review.get("report_path"),
            "thesis_status": review.get("thesis_status"),
            "health_score": review.get("health_score"),
            "last_review_date": review.get("reviewed_at"),
            "next_review_date": review.get("next_review_date"),
            "review_action": review.get("review_action"),
            "metrics": review.get("metrics") or [],
            "research_evidence": review.get("evidence") or [],
            "research_provenance": review.get("provenance"),
        })
    elif status == "unreviewed" and allow_legacy:
        projection["research_binding_status"] = "runtime_legacy"
    else:
        projection.update({
            "thesis_status": "not_established",
            "health_score": None,
            "last_review_date": None,
            "next_review_date": None,
            "review_action": None,
            "metrics": [],
            "research_evidence": [],
        })
    return projection


def identity_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def news_event_id(event: dict[str, Any]) -> str:
    fields = ("position_id", "date", "source_identity", "content_sha256",
              "review_required", "attribution_status", "covers_alert_id",
              "quote_identity", "quote_content_sha256")
    return "news:" + identity_sha256({key: event.get(key) for key in fields})


def event_identity_complete(event: dict[str, Any]) -> bool:
    return bool(
        event.get("position_id") and event.get("source_identity")
        and _valid_date(event.get("date"))
        and SHA256_RE.fullmatch(str(event.get("content_sha256") or ""))
        and event.get("event_id") == news_event_id(event)
    )


def event_evidence_status(event: dict[str, Any], repo_root: Path) -> str:
    if not event_identity_complete(event):
        return "identity_missing"
    root = repo_root.resolve()
    report = (root / str(event.get("report_path") or "")).resolve()
    if root not in report.parents or not report.is_file():
        return "report_missing"
    if report.relative_to(root).as_posix() != event.get("source_identity"):
        return "source_identity_mismatch"
    try:
        return "matched" if canonical_file_sha256(report) == event["content_sha256"] else "hash_mismatch"
    except OSError:
        return "report_unavailable"


def project_news_events(position: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    events = list(position.get("events") or [])
    if isinstance(position.get("latest_event"), dict):
        events.append(position["latest_event"])
    result = []
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        key = identity_sha256(event)
        if key in seen:
            continue
        seen.add(key)
        status = event_evidence_status(event, repo_root)
        if event.get("position_id") and event["position_id"] != position.get("position_id"):
            status = "cycle_mismatch"
        result.append({**event, "evidence_status": status})
    return result


def identity_alert(alert: dict[str, Any], reason: str) -> dict[str, Any]:
    """Keep unbound legacy data inspectable, without promoting it to research."""
    return {**alert, "kind": "identity_verification",
            "original_kind": alert.get("original_kind") or alert.get("kind"),
            "identity_status": reason, "severity": "warning",
            "title": "历史事件或提醒身份待核验",
            "detail": "事件周期、来源或证据身份待核验；尚未采用为当前持仓任务"}


def alert_identity_key(alert: dict[str, Any]) -> str:
    if alert.get("event_id"):
        return str(alert.get("kind")) + ":" + str(alert["event_id"])
    return identity_sha256({key: alert.get(key) for key in (
        "kind", "original_kind", "position_id", "source_identity", "report_path",
        "content_sha256", "event_date", "date", "quote_timestamp", "identity_status")})


def price_identity_complete(alert: dict[str, Any]) -> bool:
    evidence = alert.get("quote_evidence")
    if not isinstance(evidence, dict) or not alert.get("position_id"):
        return False
    digest = identity_sha256(evidence)
    quote_id = "quote:" + digest
    return bool(
        evidence.get("ticker") == alert.get("ticker") and evidence.get("observed_at")
        and _valid_date(alert.get("event_date")) and evidence.get("window") == alert.get("window")
        and alert.get("quote_identity") == alert.get("source_identity") == quote_id
        and alert.get("content_sha256") == digest
        and alert.get("event_id") == "price_move:" + identity_sha256(
            {"position_id": alert["position_id"], "quote_identity": quote_id})
    )


def covers_price_move(projection: dict[str, Any], alert: dict[str, Any], *, as_of: date) -> bool:
    if not price_identity_complete(alert):
        return False
    return any(
        event_identity_complete(event)
        and event.get("evidence_status") == "matched"
        and event.get("position_id") == projection.get("position_id") == alert.get("position_id")
        and event.get("attribution_status") == "completed"
        and _valid_date(str(event.get("recorded_at") or "")[:10])
        and str(event["recorded_at"])[:10] <= as_of.isoformat()
        and event.get("covers_alert_id") == alert["event_id"]
        and event.get("quote_identity") == alert["quote_identity"]
        and event.get("quote_content_sha256") == alert["content_sha256"]
        for event in projection.get("news_pulse_events") or []
    )


def covers_event(projection: dict[str, Any], event: dict[str, Any]) -> bool:
    """A later timestamp alone never closes an event; its identity must match."""
    if (projection.get("research_binding_status") != "matched"
            or not event_identity_complete(event)
            or event.get("evidence_status") != "matched"
            or event.get("position_id") != projection.get("position_id")):
        return False
    event_date = str(event.get("event_date") or event.get("date") or "")[:10]
    reviewed = str(projection.get("last_review_date") or "")
    identities = {event["source_identity"]}
    if not identities or not _valid_date(event_date) or event_date > reviewed:
        return False
    return any(
        isinstance(item, dict)
        and item.get("source_identity") in identities
        and _valid_date(item.get("date"))
        and event_date <= item["date"] <= reviewed
        and SHA256_RE.fullmatch(str(item.get("content_sha256") or ""))
        and item["content_sha256"] == event["content_sha256"]
        for item in projection.get("research_evidence", [])
    )


def pending_alerts(projection: dict[str, Any], *, as_of: date) -> list[dict[str, Any]]:
    """Recompute deadlines and retain only uncovered, same-cycle cached alerts."""
    next_review = str(projection.get("next_review_date") or "")
    alerts = []
    events = {event.get("event_id"): event for event in projection.get("news_pulse_events") or []
              if isinstance(event, dict) and event.get("event_id")}
    candidates = list(projection.get("alerts") or [])
    for event in projection.get("news_pulse_events") or []:
        if not isinstance(event, dict):
            continue
        if not event_identity_complete(event):
            candidates.append(identity_alert(event, "event_identity_missing"))
        elif event.get("review_required"):
            candidates.append({**event, "kind": "thesis_review", "severity": "critical",
                               "event_date": event["date"], "title": "异动报告要求重审论文",
                               "detail": event.get("summary") or "请复核对应事件"})
    seen = set()
    for alert in candidates:
        if not isinstance(alert, dict):
            continue
        if alert.get("kind") == "identity_verification":
            key = alert_identity_key(alert)
            if key not in seen:
                alerts.append(dict(alert))
                seen.add(key)
            continue
        if alert.get("position_id") and alert["position_id"] != projection.get("position_id"):
            continue
        is_binding_alert = (alert.get("kind") == "research_binding"
                            or (alert.get("kind") == "thesis_review" and "binding_reasons" in alert))
        if is_binding_alert and projection.get("research_binding_status") == "matched":
            continue
        if alert.get("kind") == "review_due" and next_review:
            # Cache is not authoritative for deadlines, including undated legacy alerts.
            if alert.get("due_date") == next_review and _valid_date(next_review) and as_of < date.fromisoformat(next_review):
                alerts.append(dict(alert))
            continue
        if not alert.get("position_id") or not projection.get("position_id"):
            alerts.append(identity_alert(alert, "position_id_missing"))
            continue
        if alert.get("kind") == "thesis_review" and not is_binding_alert:
            if not event_identity_complete(alert):
                alerts.append(identity_alert(alert, "event_identity_missing"))
                continue
            current = events.get(alert["event_id"])
            if current is None:
                alerts.append(identity_alert(alert, "event_authority_missing"))
                continue
            alert = {**alert, "evidence_status": current.get("evidence_status")}
        if alert.get("kind") == "price_move":
            if not price_identity_complete(alert):
                alerts.append(identity_alert(alert, "quote_identity_missing"))
                continue
            if covers_price_move(projection, alert, as_of=as_of):
                continue
        if alert.get("kind") == "thesis_review" and covers_event(projection, alert):
            continue
        key = alert_identity_key(alert)
        if key not in seen:
            alerts.append(dict(alert))
            seen.add(key)
    if _valid_date(next_review) and date.fromisoformat(next_review) <= as_of:
        alerts.append({
            "kind": "review_due", "due_date": next_review,
            "position_id": projection.get("position_id"),
            "detail": f"复核日期 {next_review}（到期或逾期）", "severity": "critical",
        })
    return alerts


def save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    upsert = subparsers.add_parser("upsert")
    upsert.add_argument("--record", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    path = root / RELATIVE_PATH
    if arguments.command == "validate":
        errors = validate_payload(load(path), repo_root=root)
        if errors:
            print("FAIL: " + "; ".join(errors))
            return 1
        print("holding research reviews=PASS")
        return 0
    record_path = arguments.record if arguments.record.is_absolute() else root / arguments.record
    record = json.loads(record_path.read_text(encoding="utf-8"))
    payload = load(path)
    key = str(record.get("position_id") or "")
    errors = validate_payload(
        {**empty_payload(), "reviews": {key: record}}, repo_root=root, allow_migration=False
    )
    tracking = json.loads((root / "data/investment-dashboard/post_buy_tracking.json").read_text(encoding="utf-8"))
    original = json.loads((root / "data/investment-dashboard/original_buy_theses.json").read_text(encoding="utf-8"))
    ticker = str(record.get("ticker") or "").upper()
    position = {**(tracking.get("positions") or {}).get(ticker, {}), "ticker": ticker}
    status, reasons = binding_status(record, position, original, root)
    if status != "matched":
        errors.extend(reasons)
    if errors:
        raise ValueError("invalid holding research review: " + "; ".join(errors))
    if date.fromisoformat(record["reviewed_at"]) > date.today():
        raise ValueError("reviewed_at cannot be in the future")
    payload.setdefault("reviews", {})[key] = record
    errors = validate_payload(payload, repo_root=root)
    if errors:
        raise ValueError("invalid holding research review: " + "; ".join(errors))
    save(path, payload)
    print(f"Saved holding research review: {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
