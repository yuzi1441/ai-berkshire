#!/usr/bin/env python3
"""Manage the optional post-buy tracking layer for the investment dashboard.

The source of truth is ``data/investment-dashboard/post_buy_tracking.json``.
It is intentionally separate from fundamental reports: a recommendation to buy
does not imply that a position exists. A position enters this layer only when
the user explicitly registers it after buying.

Examples::

    python3 tools/post_buy_tracking.py register \
      --ticker 600406.SH --company 国电南瑞 --market A股 \
      --buy-date 2026-08-01 --next-review 2026-11-01 \
      --thesis-report reports/国电南瑞/国电南瑞-thesis.md
    python3 tools/post_buy_tracking.py update 600406.SH \
      --thesis-status healthy --health-score 8 --last-review 2026-08-01
    python3 tools/post_buy_tracking.py event 600406.SH \
      --change-pct -6.4 --window 1日 --category 情绪 \
      --summary "大盘与行业同步回撤，暂未发现公司特有事件" \
      --no-review-required
    python3 tools/post_buy_tracking.py check
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from source_hash import canonical_file_sha256


ROOT = Path(__file__).resolve().parents[1]
TRACKING_RELATIVE = Path("data/investment-dashboard/post_buy_tracking.json")
ORIGINAL_THESIS_RELATIVE = Path("data/investment-dashboard/original_buy_theses.json")
ALERTS_RELATIVE = Path("data/investment-dashboard/post_buy_alerts.json")
SITE_ALERTS_RELATIVE = Path("site/data/post_buy_alerts.json")
SHANGHAI = ZoneInfo("Asia/Shanghai")
SCHEMA_VERSION = 1
MARKETS = ("A股", "港股", "美股", "未识别")
POSITION_STATUSES = ("holding", "paused", "closed")
THESIS_STATUSES = ("not_established", "healthy", "borderline", "damaged", "broken")
EVENT_CATEGORIES = ("基本面", "行业", "情绪", "技术", "混合", "不明")
DEFAULT_THRESHOLDS = {"daily_pct": 5.0, "review_days_before": 7}
ORIGINAL_THESIS_SCHEMA_VERSION = 2


def today() -> date:
    return datetime.now(SHANGHAI).date()


def iso_now() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def parse_iso_date(value: str | None, field: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must use YYYY-MM-DD: {value}") from error
    return value


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default.copy()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected an object: {path}")
    return payload


def load_tracking(path: Path) -> dict[str, Any]:
    payload = load_json(path, {"schema_version": SCHEMA_VERSION, "positions": {}})
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported tracking schema: {payload.get('schema_version')}")
    positions = payload.get("positions")
    if not isinstance(positions, dict):
        raise ValueError("post_buy_tracking.positions must be an object")
    history = payload.get("position_history", [])
    if not isinstance(history, list):
        raise ValueError("post_buy_tracking.position_history must be a list")
    return payload


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def key_for_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker cannot be empty")
    return normalized


def position_id_for(position_record: dict[str, Any]) -> str:
    """Return the stable identity for one buy-to-close position cycle."""
    ticker = key_for_ticker(str(position_record.get("ticker") or ""))
    buy_date = str(position_record.get("buy_date") or "").strip()
    return f"{ticker}:{buy_date}" if buy_date else f"{ticker}:legacy"


def position(payload: dict[str, Any], ticker: str) -> dict[str, Any]:
    key = key_for_ticker(ticker)
    item = payload["positions"].get(key)
    if not isinstance(item, dict):
        raise ValueError(f"No post-buy position registered for {key}")
    return item


def default_position(args: argparse.Namespace) -> dict[str, Any]:
    buy_date = parse_iso_date(args.buy_date, "buy-date")
    if not buy_date:
        raise ValueError("--buy-date is required")
    next_review = parse_iso_date(args.next_review, "next-review")
    metrics = json.loads(args.metrics) if args.metrics else []
    if not isinstance(metrics, list):
        raise ValueError("--metrics must be a JSON list")
    return {
        "company": args.company,
        "ticker": key_for_ticker(args.ticker),
        "position_id": f"{key_for_ticker(args.ticker)}:{buy_date}",
        "market": args.market,
        "status": "holding",
        "buy_date": buy_date,
        "cost_basis": args.cost_basis,
        "position_weight": args.position_weight,
        "thesis_report_path": args.thesis_report,
        "thesis_status": "not_established",
        "health_score": None,
        "last_review_date": None,
        "next_review_date": next_review,
        "review_action": None,
        "metrics": metrics,
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "events": [],
        "latest_event": None,
        "updated_at": iso_now(),
    }


def archive_position(payload: dict[str, Any], ticker: str, *, reason: str) -> dict[str, Any] | None:
    """Move the replaced current position into immutable cycle history."""
    key = key_for_ticker(ticker)
    existing = payload["positions"].get(key)
    if not isinstance(existing, dict):
        return None
    archived = copy.deepcopy(existing)
    archived["position_id"] = archived.get("position_id") or position_id_for(archived)
    archived["status"] = "closed"
    archived.setdefault("closed_at", iso_now())
    archived.setdefault("close_reason", reason)
    history = [
        item
        for item in payload.setdefault("position_history", [])
        if not isinstance(item, dict) or item.get("position_id") != archived["position_id"]
    ]
    history.append(archived)
    payload["position_history"] = history
    return archived


def _empty_original_thesis_payload() -> dict[str, Any]:
    return {
        "schema_version": ORIGINAL_THESIS_SCHEMA_VERSION,
        "cycles": {},
        "active_position_ids": {},
    }


def load_original_thesis(path: Path) -> dict[str, Any]:
    """Load and validate either the legacy or cycle-bound thesis schema."""
    payload = load_json(path, _empty_original_thesis_payload())
    version = payload.get("schema_version", 1)
    if version == 1:
        if not isinstance(payload.get("positions"), dict):
            raise ValueError("original_buy_theses.positions must be an object")
        return payload
    if version == ORIGINAL_THESIS_SCHEMA_VERSION:
        if not isinstance(payload.get("cycles"), dict):
            raise ValueError("original_buy_theses.cycles must be an object")
        if not isinstance(payload.get("active_position_ids"), dict):
            raise ValueError("original_buy_theses.active_position_ids must be an object")
        return payload
    raise ValueError(f"Unsupported original thesis schema: {version}")


def _original_thesis_cycles(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    cycles = payload.get("cycles")
    if not isinstance(cycles, dict):
        cycles = {}
        payload["cycles"] = cycles
    active = payload.get("active_position_ids")
    if not isinstance(active, dict):
        active = {}
        payload["active_position_ids"] = active
    payload["schema_version"] = ORIGINAL_THESIS_SCHEMA_VERSION
    return cycles, active


def _close_thesis_cycle(record: dict[str, Any], *, timestamp: str, reason: str) -> None:
    record["position_status"] = "closed"
    record.setdefault("closed_at", timestamp)
    record.setdefault("close_reason", reason)


def archive_original_buy_thesis(
    repo_root: Path,
    position_record: dict[str, Any],
    *,
    timestamp: str | None = None,
    write: bool = True,
    reason: str = "new_purchase_cycle",
) -> dict[str, Any]:
    """Close the current thesis cycle before a ticker is registered again."""
    root = repo_root.resolve()
    snapshot_path = root / ORIGINAL_THESIS_RELATIVE
    payload = load_original_thesis(snapshot_path)
    stamp = timestamp or iso_now()
    result = _archive_original_buy_thesis_payload(
        payload,
        position_record,
        timestamp=stamp,
        reason=reason,
    )
    if result["status"] != "no_baseline" and write:
        save_json(snapshot_path, payload)
    result["written"] = bool(result["status"] != "no_baseline" and write)
    return result


def _archive_original_buy_thesis_payload(
    payload: dict[str, Any],
    position_record: dict[str, Any],
    *,
    timestamp: str,
    reason: str,
) -> dict[str, Any]:
    """Archive a cycle in memory without changing the filesystem."""
    ticker = key_for_ticker(str(position_record.get("ticker") or ""))
    cycles, active = _original_thesis_cycles(payload)
    cycle_id = str(active.get(ticker) or position_id_for(position_record))
    changed = False
    existing = cycles.get(cycle_id)
    if isinstance(existing, dict):
        _close_thesis_cycle(existing, timestamp=timestamp, reason=reason)
        changed = True
    legacy_positions = payload.get("positions")
    if isinstance(legacy_positions, dict):
        legacy = legacy_positions.pop(ticker, None)
        if isinstance(legacy, dict):
            legacy = copy.deepcopy(legacy)
            legacy["position_id"] = cycle_id
            _close_thesis_cycle(legacy, timestamp=timestamp, reason=reason)
            cycles[cycle_id] = legacy
            changed = True
        if not legacy_positions:
            payload.pop("positions", None)
    if active.get(ticker) == cycle_id:
        active.pop(ticker, None)
        changed = True
    return {
        "status": "archived" if changed else "no_baseline",
        "ticker": ticker,
        "position_id": cycle_id,
    }


def _thesis_summary(
    status: str,
    ticker: str,
    position_id: str,
    record: dict[str, Any],
    current_hash: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "ticker": ticker,
        "position_id": position_id,
        "source_report": record.get("source_report"),
        "source_hash": record.get("source_hash"),
        "current_source_hash": current_hash,
        "source_changed_since_capture": record.get("source_hash") != current_hash,
        "captured_at": record.get("captured_at"),
        "provenance": record.get("provenance") or "unknown",
        "backfilled": bool(record.get("backfilled", False)),
    }


def _freeze_original_buy_thesis_payload(
    payload: dict[str, Any],
    position_record: dict[str, Any],
    *,
    report_path: Path,
    repo_root: Path,
    current_hash: str,
    current_text: str,
    timestamp: str,
    provenance: str,
    backfilled: bool,
    persisted: bool,
) -> dict[str, Any]:
    """Construct one thesis cycle in memory; the caller controls persistence."""
    root = repo_root.resolve()
    ticker = key_for_ticker(str(position_record.get("ticker") or ""))
    position_id = str(position_record.get("position_id") or position_id_for(position_record))
    cycles, active = _original_thesis_cycles(payload)

    existing = cycles.get(position_id)
    if isinstance(existing, dict):
        if active.get(ticker) != position_id:
            active[ticker] = position_id
        return _thesis_summary("frozen", ticker, position_id, existing, current_hash)

    stamp = timestamp
    previous_id = str(active.get(ticker) or "")
    if previous_id and previous_id != position_id:
        previous = cycles.get(previous_id)
        if isinstance(previous, dict):
            _close_thesis_cycle(previous, timestamp=stamp, reason="new_purchase_cycle")
        active.pop(ticker, None)

    # Migrate the pre-cycle schema without overwriting its evidence.  When the
    # legacy baseline has no known prior cycle, it is the current cycle's
    # historical baseline; an existing active cycle is instead archived.
    legacy_positions = payload.get("positions")
    legacy = legacy_positions.get(ticker) if isinstance(legacy_positions, dict) else None
    if isinstance(legacy, dict):
        legacy = copy.deepcopy(legacy)
        legacy_id = str(legacy.get("position_id") or previous_id or position_id)
        if legacy_id == position_id and not previous_id:
            legacy["position_id"] = position_id
            legacy["ticker"] = ticker
            legacy["buy_date"] = position_record.get("buy_date")
            legacy["position_status"] = position_record.get("status") or "holding"
            cycles[position_id] = legacy
            active[ticker] = position_id
            legacy_positions.pop(ticker, None)
            if not legacy_positions:
                payload.pop("positions", None)
            return _thesis_summary("frozen", ticker, position_id, legacy, current_hash)
        _close_thesis_cycle(legacy, timestamp=stamp, reason="new_purchase_cycle")
        legacy["position_id"] = legacy_id
        cycles[legacy_id] = legacy
        legacy_positions.pop(ticker, None)
        if not legacy_positions:
            payload.pop("positions", None)

    record = {
        "company": position_record.get("company"),
        "ticker": ticker,
        "position_id": position_id,
        "buy_date": position_record.get("buy_date"),
        "position_status": position_record.get("status") or "holding",
        "market": position_record.get("market"),
        "source_report": report_path.relative_to(root).as_posix(),
        "source_hash": current_hash,
        "source_text": current_text,
        "captured_at": stamp,
        "provenance": provenance,
        "backfilled": bool(backfilled),
    }
    cycles[position_id] = record
    active[ticker] = position_id
    return _thesis_summary(
        "backfilled" if backfilled and persisted else "would_backfill" if backfilled else "captured" if persisted else "would_capture",
        ticker,
        position_id,
        record,
        current_hash,
    )


def freeze_original_buy_thesis(
    repo_root: Path,
    position_record: dict[str, Any],
    *,
    timestamp: str | None = None,
    write: bool = True,
    provenance: str = "purchase_registration",
    backfilled: bool = False,
) -> dict[str, Any]:
    """Freeze the thesis as part of registering a real position.

    Existing baselines are immutable.  ``backfilled`` is explicit so a
    historical Holding repaired later cannot be mistaken for a purchase-time
    snapshot.
    """
    root = repo_root.resolve()
    ticker = key_for_ticker(str(position_record.get("ticker") or ""))
    position_id = str(position_record.get("position_id") or position_id_for(position_record))
    raw_report = position_record.get("thesis_report_path")
    if not raw_report:
        return {"status": "missing_thesis_report_path", "ticker": ticker, "position_id": position_id}
    report_path = (root / str(raw_report)).resolve()
    if not report_path.is_file() or root not in report_path.parents:
        return {
            "status": "missing_thesis_report",
            "ticker": ticker,
            "position_id": position_id,
            "source_report": str(raw_report),
        }

    current_hash = canonical_file_sha256(report_path)
    current_text = report_path.read_text(encoding="utf-8", errors="replace")
    snapshot_path = root / ORIGINAL_THESIS_RELATIVE
    payload = load_original_thesis(snapshot_path)
    before = copy.deepcopy(payload)
    result = _freeze_original_buy_thesis_payload(
        payload,
        position_record,
        report_path=report_path,
        repo_root=root,
        current_hash=current_hash,
        current_text=current_text,
        timestamp=timestamp or iso_now(),
        provenance=provenance,
        backfilled=backfilled,
        persisted=write,
    )
    if write and payload != before:
        save_json(snapshot_path, payload)
    return result


def _read_thesis_source(repo_root: Path, position_record: dict[str, Any]) -> tuple[Path, str, str]:
    """Read and hash a thesis before any registration payload is changed."""
    raw_report = position_record.get("thesis_report_path")
    if not raw_report:
        raise ValueError("register requires --thesis-report so the purchase-time Original Buy Thesis can be frozen")
    report_path = (repo_root.resolve() / str(raw_report)).resolve()
    if not report_path.is_file() or repo_root.resolve() not in report_path.parents:
        raise ValueError(f"cannot read thesis report: {raw_report}")
    text = report_path.read_text(encoding="utf-8", errors="replace")
    return report_path, canonical_file_sha256(report_path), text


def _snapshot_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _restore_bytes(path: Path, content: bytes | None) -> None:
    """Restore one file atomically, including the originally-absent case."""
    if content is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.rollback.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _commit_registration_payloads(
    tracking_path: Path,
    tracking_payload: dict[str, Any],
    thesis_path: Path,
    thesis_payload: dict[str, Any],
) -> None:
    """Write the two registration sources together and rollback on failure."""
    originals = {
        tracking_path: _snapshot_bytes(tracking_path),
        thesis_path: _snapshot_bytes(thesis_path),
    }
    try:
        save_json(tracking_path, tracking_payload)
        save_json(thesis_path, thesis_payload)
    except Exception as error:
        try:
            for path, content in originals.items():
                _restore_bytes(path, content)
        except Exception as rollback_error:
            raise OSError(f"re-entry registration failed and rollback failed: {rollback_error}") from error
        raise OSError(f"re-entry registration rolled back: {error}") from error


def command_register(args: argparse.Namespace, repo_root: Path) -> None:
    path = repo_root / TRACKING_RELATIVE
    payload = load_tracking(path)
    key = key_for_ticker(args.ticker)
    if key in payload["positions"] and not args.force:
        raise ValueError(f"Position already exists: {key}; use --force to replace it")
    registered = default_position(args)
    existing = payload["positions"].get(key)
    report_path, current_hash, current_text = _read_thesis_source(repo_root, registered)
    thesis_path = repo_root / ORIGINAL_THESIS_RELATIVE
    original_payload = load_original_thesis(thesis_path)
    original_cycles, _ = _original_thesis_cycles(original_payload)
    registered_id = str(registered.get("position_id") or "")
    if registered_id != position_id_for(registered):
        raise ValueError(f"invalid position_id for {key}: {registered_id}")
    if registered_id in original_cycles:
        raise ValueError(f"Position cycle already exists: {registered_id}")
    if existing and args.force:
        existing_id = str(existing.get("position_id") or position_id_for(existing))
        if existing_id == registered_id:
            raise ValueError("--force must use a new --buy-date to create a new holding cycle")
    staged_tracking = copy.deepcopy(payload)
    staged_original = copy.deepcopy(original_payload)
    if existing and args.force:
        archive_position(staged_tracking, key, reason="replaced_by_new_purchase_cycle")
        _archive_original_buy_thesis_payload(
            staged_original,
            existing,
            timestamp=registered["updated_at"],
            reason="replaced_by_new_purchase_cycle",
        )
    captured = _freeze_original_buy_thesis_payload(
        staged_original,
        registered,
        report_path=report_path,
        repo_root=repo_root,
        current_hash=current_hash,
        current_text=current_text,
        timestamp=registered["updated_at"],
        provenance="purchase_registration",
        backfilled=False,
        persisted=True,
    )
    staged_tracking["positions"][key] = registered
    staged_tracking["updated_at"] = iso_now()
    _commit_registration_payloads(path, staged_tracking, thesis_path, staged_original)
    print(f"Registered post-buy tracking: {key}; Original Buy Thesis {captured.get('status')}")


def command_update(args: argparse.Namespace, repo_root: Path) -> None:
    path = repo_root / TRACKING_RELATIVE
    payload = load_tracking(path)
    item = position(payload, args.ticker)
    updates: dict[str, Any] = {}
    for source, target in (
        (args.status, "status"),
        (args.thesis_status, "thesis_status"),
        (args.health_score, "health_score"),
        (args.last_review, "last_review_date"),
        (args.next_review, "next_review_date"),
        (args.review_action, "review_action"),
        (args.thesis_report, "thesis_report_path"),
    ):
        if source is not None:
            updates[target] = source
    if "status" in updates and updates["status"] not in POSITION_STATUSES:
        raise ValueError(f"status must be one of {POSITION_STATUSES}")
    if "thesis_status" in updates and updates["thesis_status"] not in THESIS_STATUSES:
        raise ValueError(f"thesis-status must be one of {THESIS_STATUSES}")
    if "health_score" in updates:
        score = float(updates["health_score"])
        if score < 1 or score > 10:
            raise ValueError("health-score must be between 1 and 10")
        updates["health_score"] = score if not score.is_integer() else int(score)
    for field in ("last_review_date", "next_review_date"):
        if field in updates:
            updates[field] = parse_iso_date(updates[field], field)
    if args.metrics is not None:
        metrics = json.loads(args.metrics)
        if not isinstance(metrics, list):
            raise ValueError("--metrics must be a JSON list")
        updates["metrics"] = metrics
    item.update(updates)
    item["updated_at"] = iso_now()
    payload["updated_at"] = iso_now()
    save_json(path, payload)
    if updates.get("status") == "closed":
        archive_original_buy_thesis(
            repo_root,
            item,
            timestamp=item["updated_at"],
            write=True,
            reason="position_closed",
        )
    print(f"Updated post-buy tracking: {key_for_ticker(args.ticker)}")


def command_event(args: argparse.Namespace, repo_root: Path) -> None:
    path = repo_root / TRACKING_RELATIVE
    payload = load_tracking(path)
    try:
        item = position(payload, args.ticker)
    except ValueError:
        if args.skip_unregistered:
            print(f"Skipped event; no registered post-buy position: {key_for_ticker(args.ticker)}")
            return
        raise
    event_date = parse_iso_date(args.event_date, "event-date") or today().isoformat()
    event = {
        "date": event_date,
        "change_pct": args.change_pct,
        "window": args.window,
        "category": args.category,
        "summary": args.summary,
        "review_required": bool(args.review_required),
        "report_path": args.report_path,
    }
    events = item.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("position.events must be a list")
    events.append(event)
    item["events"] = events[-50:]
    item["latest_event"] = event
    item["updated_at"] = iso_now()
    payload["updated_at"] = iso_now()
    save_json(path, payload)
    print(f"Added post-buy event: {key_for_ticker(args.ticker)} {event_date}")


def load_quotes(repo_root: Path, quote_path: Path | None) -> dict[str, dict[str, Any]]:
    candidates = [quote_path] if quote_path else [
        repo_root / "data/investment-dashboard/quotes/latest.json",
        repo_root / "site/data/quotes/latest.json",
    ]
    for candidate in candidates:
        if not candidate or not candidate.exists():
            continue
        payload = load_json(candidate, {})
        quotes = payload.get("quotes")
        if not isinstance(quotes, list):
            continue
        return {
            str(item.get("ticker")).upper(): item
            for item in quotes
            if isinstance(item, dict) and item.get("ticker")
        }
    return {}


def command_check(args: argparse.Namespace, repo_root: Path) -> None:
    tracking_path = repo_root / TRACKING_RELATIVE
    payload = load_tracking(tracking_path)
    as_of = date.fromisoformat(args.as_of) if args.as_of else today()
    quotes = load_quotes(repo_root, args.quote_path)
    alerts: list[dict[str, Any]] = []

    for key, item in payload["positions"].items():
        if not isinstance(item, dict) or item.get("status") != "holding":
            continue
        thresholds = item.get("thresholds") if isinstance(item.get("thresholds"), dict) else {}
        daily_pct = float(thresholds.get("daily_pct", DEFAULT_THRESHOLDS["daily_pct"]))
        review_days = int(thresholds.get("review_days_before", DEFAULT_THRESHOLDS["review_days_before"]))
        next_review = item.get("next_review_date")
        if next_review:
            review_date = date.fromisoformat(next_review)
            days_left = (review_date - as_of).days
            if days_left <= review_days:
                alerts.append(
                    {
                        "ticker": key,
                        "company": item.get("company", key),
                        "kind": "review_due",
                        "severity": "critical" if days_left <= 0 else "warning",
                        "title": "论文复核已到期" if days_left <= 0 else "论文复核即将到期",
                        "detail": f"复核日期 {next_review}（{'逾期' if days_left < 0 else f'{days_left} 天后'}）",
                        "due_date": next_review,
                    }
                )
        quote = quotes.get(key)
        change = quote.get("change_pct") if isinstance(quote, dict) else None
        if isinstance(change, (int, float)) and abs(float(change)) >= daily_pct:
            alerts.append(
                {
                    "ticker": key,
                    "company": item.get("company", key),
                    "kind": "price_move",
                    "severity": "critical" if abs(float(change)) >= daily_pct * 2 else "warning",
                    "title": "股价异动待分析",
                    "detail": f"单日涨跌 {float(change):+.2f}%，达到 ±{daily_pct:g}% 预警线",
                    "change_pct": float(change),
                    "quote_timestamp": quote.get("provider_timestamp"),
                }
            )
        latest_event = item.get("latest_event")
        if isinstance(latest_event, dict) and latest_event.get("review_required"):
            alerts.append(
                {
                    "ticker": key,
                    "company": item.get("company", key),
                    "kind": "thesis_review",
                    "severity": "critical",
                    "title": "异动报告要求重审论文",
                    "detail": latest_event.get("summary") or "请运行 thesis-tracker",
                    "event_date": latest_event.get("date"),
                    "report_path": latest_event.get("report_path"),
                }
            )

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": iso_now(),
        "as_of": as_of.isoformat(),
        "alert_count": len(alerts),
        "alerts": alerts,
    }
    save_json(repo_root / ALERTS_RELATIVE, result)
    save_json(repo_root / SITE_ALERTS_RELATIVE, result)
    print(f"Generated {len(alerts)} post-buy alerts for {len(payload['positions'])} registered positions.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="register a position after the user confirms a purchase")
    register.add_argument("--ticker", required=True)
    register.add_argument("--company", required=True)
    register.add_argument("--market", required=True, choices=MARKETS)
    register.add_argument("--buy-date", required=True)
    register.add_argument("--cost-basis", type=float)
    register.add_argument("--position-weight", type=float, help="portfolio weight in percent, e.g. 5 for 5 percent")
    register.add_argument("--next-review")
    register.add_argument("--thesis-report")
    register.add_argument("--metrics", help="JSON list of 3-5 tracked metrics")
    register.add_argument("--force", action="store_true")
    register.set_defaults(handler=command_register)

    update = sub.add_parser("update", help="update thesis or review state")
    update.add_argument("ticker")
    update.add_argument("--status", choices=POSITION_STATUSES)
    update.add_argument("--thesis-status", choices=THESIS_STATUSES)
    update.add_argument("--health-score", type=float)
    update.add_argument("--last-review")
    update.add_argument("--next-review")
    update.add_argument("--review-action")
    update.add_argument("--thesis-report")
    update.add_argument("--metrics", help="JSON list of 3-5 tracked metrics")
    update.set_defaults(handler=command_update)

    event = sub.add_parser("event", help="append a manually reviewed price/news event")
    event.add_argument("ticker")
    event.add_argument("--event-date")
    event.add_argument("--change-pct", type=float)
    event.add_argument("--window", default="1日")
    event.add_argument("--category", choices=EVENT_CATEGORIES, default="不明")
    event.add_argument("--summary", required=True)
    event.add_argument("--review-required", action="store_true")
    event.add_argument("--no-review-required", dest="review_required", action="store_false")
    event.set_defaults(review_required=False)
    event.add_argument("--report-path")
    event.add_argument("--skip-unregistered", action="store_true", help="exit successfully when the stock is not a registered position")
    event.set_defaults(handler=command_event)

    check = sub.add_parser("check", help="generate due-date and price-move alerts")
    check.add_argument("--as-of")
    check.add_argument("--quote-path", type=Path)
    check.set_defaults(handler=command_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    try:
        args.handler(args, repo_root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
