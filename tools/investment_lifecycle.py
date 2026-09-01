"""Shared lifecycle, thesis-drift, and Checklist contracts for the dashboard.

The dashboard is deliberately report-compatible: old reports can still supply
the fundamental conclusion, while this module supplies the small, explicit
state machine that determines what work is allowed next.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


LIFECYCLE_STATES = ("WATCH", "PRE_BUY", "HOLDING", "EXITED")
WATCH_ACTIONS = ("KEEP WATCH", "RUN CHECKLIST", "DROP")
HOLDING_ACTIONS = ("ADD", "HOLD", "REDUCE", "EXIT")
DRIFT_DIRECTIONS = ("improved", "unchanged", "weakened")
DRIFT_SEVERITIES = ("none", "minor", "major")
CHECKLIST_STATUSES = ("not_run", "pass", "conditional_pass", "fail", "stale")

DEFAULT_REVIEW_FREQUENCY = {
    "WATCH": "180d",
    "PRE_BUY": "30d",
    "HOLDING": "quarterly",
    "EXITED": "archived",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def normalize_lifecycle(value: Any, default: str = "WATCH") -> str:
    candidate = _text(value).upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "观察": "WATCH",
        "观察池": "WATCH",
        "待买入": "PRE_BUY",
        "买入前": "PRE_BUY",
        "持仓": "HOLDING",
        "已持仓": "HOLDING",
        "已退出": "EXITED",
        "退出": "EXITED",
    }
    candidate = aliases.get(candidate, candidate)
    return candidate if candidate in LIFECYCLE_STATES else default


def normalize_checklist_status(value: Any, *, checked_at: str | None = None, as_of: date | None = None) -> str:
    """Map legacy Chinese Checklist labels to the lifecycle contract."""
    text = _text(value)
    mapping = {
        "通过": "pass",
        "pass": "pass",
        "条件通过": "conditional_pass",
        "灰色地带": "conditional_pass",
        "conditional_pass": "conditional_pass",
        "未通过": "fail",
        "否决": "fail",
        "fail": "fail",
        "stale": "stale",
        "过期": "stale",
        "待复核": "not_run",
        "未检查": "not_run",
        "missing": "not_run",
        "not_run": "not_run",
    }
    result = mapping.get(text, "not_run")
    if result != "not_run" and as_of and checked_at:
        try:
            checked = date.fromisoformat(str(checked_at)[:10])
        except ValueError:
            checked = None
        if checked and (as_of - checked).days > 180:
            return "stale"
    return result


def normalize_drift_record(value: Any = None, *, default_next_review: str | None = None) -> dict[str, Any]:
    """Return a bounded, display-safe drift record.

    The record is intentionally useful even when no drift run has happened:
    ``status=not_checked`` is different from a healthy/unchanged conclusion.
    """
    source = value if isinstance(value, dict) else {}
    checked_at = source.get("last_checked") or source.get("checked_at")
    direction = _text(source.get("direction") or "unchanged")
    if direction not in DRIFT_DIRECTIONS:
        direction = "unchanged"
    severity = _text(source.get("severity") or "none")
    if severity not in DRIFT_SEVERITIES:
        severity = "none"
    met = _number(source.get("buy_conditions_met"))
    total = _number(source.get("buy_conditions_total"))
    if met is not None:
        met = max(0, int(met))
    if total is not None:
        total = max(0, int(total))
    affected = source.get("affected_sections")
    if not isinstance(affected, list):
        affected = []
    affected = [_text(item) for item in affected if _text(item)][:8]
    history = source.get("history")
    if not isinstance(history, list):
        history = []
    history = [item for item in history if isinstance(item, dict)][-12:]
    status = _text(source.get("status")) or ("checked" if checked_at else "not_checked")
    if status not in {"not_checked", "checked", "stale"}:
        status = "checked" if checked_at else "not_checked"
    return {
        "status": status,
        "direction": direction,
        "severity": severity,
        "action": _text(source.get("action")) or None,
        "buy_conditions_met": met,
        "buy_conditions_total": total,
        "patch_required": source.get("patch_required") is True,
        "affected_sections": affected,
        "last_checked": checked_at,
        "next_review": source.get("next_review") or default_next_review,
        "summary": _text(source.get("summary")),
        "source": _text(source.get("source")) or "structured_drift",
        "history": history,
    }


def derive_watch_action(drift: dict[str, Any] | None) -> str:
    """Return the only three actions allowed before an actual purchase."""
    record = normalize_drift_record(drift)
    direction = record["direction"]
    severity = record["severity"]
    met = record["buy_conditions_met"]
    total = record["buy_conditions_total"]
    if direction == "weakened" and severity == "major":
        return "DROP"
    if total is not None and total > 0 and met is not None and met >= total:
        return "RUN CHECKLIST"
    if direction == "improved" and severity in {"none", "minor"}:
        return "RUN CHECKLIST" if total is not None and total > 0 else "KEEP WATCH"
    return "KEEP WATCH"


def derive_holding_action(
    tracking: dict[str, Any] | None,
    drift: dict[str, Any] | None,
) -> str:
    """Map the original buy thesis and current drift to ADD/HOLD/REDUCE/EXIT."""
    position = tracking if isinstance(tracking, dict) else {}
    record = normalize_drift_record(drift)
    thesis_status = _text(position.get("thesis_status"))
    if position.get("red_line_triggered") is True or thesis_status == "broken":
        return "EXIT"
    if record["severity"] == "major" and record["direction"] == "weakened":
        return "REDUCE"
    if thesis_status in {"damaged"}:
        return "REDUCE"
    if position.get("add_ready") is True and record["direction"] == "improved":
        return "ADD"
    return "HOLD"


def classify_lifecycle(
    *,
    tracking: dict[str, Any] | None = None,
    lifecycle_record: dict[str, Any] | None = None,
    default: str = "WATCH",
) -> tuple[str, str]:
    """Resolve state with confirmed post-buy records as the source of truth."""
    position = tracking if isinstance(tracking, dict) else {}
    status = _text(position.get("status")).lower()
    if status == "closed" or status == "exited":
        return "EXITED", "post_buy_tracking"
    if status in {"holding", "paused"}:
        return "HOLDING", "post_buy_tracking"
    explicit = lifecycle_record if isinstance(lifecycle_record, dict) else {}
    explicit_state = explicit.get("lifecycle") or explicit.get("state")
    if explicit_state:
        state = normalize_lifecycle(explicit_state, default)
        return state, "lifecycle_record"
    return normalize_lifecycle(default), "default_watch"


def review_frequency(state: str, explicit: Any = None) -> str:
    candidate = _text(explicit)
    return candidate or DEFAULT_REVIEW_FREQUENCY.get(normalize_lifecycle(state), "180d")


def _as_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def next_review_date(state: str, *, explicit: Any = None, base: Any = None) -> str | None:
    """Compute only the lightweight default; explicit tracking dates win."""
    explicit_date = _as_date(explicit)
    if explicit_date:
        return explicit_date.isoformat()
    if normalize_lifecycle(state) == "EXITED":
        return None
    base_date = _as_date(base) or date.today()
    frequency = review_frequency(state)
    if frequency.endswith("d"):
        try:
            return (base_date + timedelta(days=int(frequency[:-1]))).isoformat()
        except ValueError:
            return None
    return None


def lifecycle_action(
    state: str,
    *,
    tracking: dict[str, Any] | None = None,
    drift: dict[str, Any] | None = None,
) -> str:
    normalized = normalize_lifecycle(state)
    if normalized == "PRE_BUY":
        record = normalize_drift_record(drift)
        return "DROP" if record["direction"] == "weakened" and record["severity"] == "major" else "RUN CHECKLIST"
    if normalized == "WATCH":
        return derive_watch_action(drift)
    if normalized == "HOLDING":
        return derive_holding_action(tracking, drift)
    return "EXITED"


def lifecycle_action_key(state: str, action: str) -> str:
    """Return the machine-readable action used by the watch contract."""
    if normalize_lifecycle(state) in {"WATCH", "PRE_BUY"}:
        return {
            "KEEP WATCH": "keep_watch",
            "RUN CHECKLIST": "run_checklist",
            "DROP": "drop",
        }.get(action, "keep_watch")
    return action


def lifecycle_contract(
    state: str,
    *,
    tracking: dict[str, Any] | None = None,
    drift: dict[str, Any] | None = None,
    explicit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the fields shared by board, static detail files, and validators."""
    explicit = explicit if isinstance(explicit, dict) else {}
    normalized = normalize_lifecycle(state)
    drift_record = normalize_drift_record(
        drift,
        default_next_review=explicit.get("next_review_date"),
    )
    action = lifecycle_action(normalized, tracking=tracking, drift=drift_record)
    next_review = (
        (tracking or {}).get("next_review_date")
        or explicit.get("next_review_date")
        or drift_record.get("next_review")
    )
    return {
        "lifecycle": normalized,
        "lifecycle_source": explicit.get("source") or "derived",
        "review_frequency": review_frequency(normalized, explicit.get("review_frequency")),
        "next_review_date": next_review_date(normalized, explicit=next_review),
        "next_action": action,
        "action": lifecycle_action_key(normalized, action),
        "drift": drift_record,
    }
