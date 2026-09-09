#!/usr/bin/env python3
"""Runtime-only human dispositions for exact investment-task fingerprints."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
FILENAME = "manual_investment_dispositions.json"
ALL_DISPOSITIONS = {
    "keep_watch",
    "redo_research",
    "formal_drift",
    "archive_drop",
}
DISPOSITION_EFFECT_CODES = {
    "keep_watch": "KEEP_WATCH",
    "redo_research": "REDO_RESEARCH",
    "formal_drift": "FORMAL_DRIFT_REQUESTED",
    "archive_drop": "USER_REQUESTED_ARCHIVE",
}
DISPOSITION_OPTIONS = {
    "reviewed_thesis_weakened": [
        "keep_watch", "redo_research", "formal_drift", "archive_drop",
    ],
    "confirmed_redline": ["formal_drift"],
}


class DispositionError(ValueError):
    """Invalid, stale, or conflicting human disposition."""


class DispositionConflict(DispositionError):
    """An exact task fingerprint already has a different disposition."""


def empty_payload() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "runtime_human_disposition_authority",
        "records": [],
    }


def allowed_dispositions(company: dict[str, Any]) -> list[str]:
    projected = company.get("manual_disposition")
    if isinstance(projected, dict) and isinstance(projected.get("allowed_options"), list):
        options = [str(item) for item in projected["allowed_options"]]
        if all(item in ALL_DISPOSITIONS for item in options):
            return options
    guidance = company.get("action_guidance")
    if not isinstance(guidance, dict) or guidance.get("requires_user_action") is not True:
        return []
    return list(DISPOSITION_OPTIONS.get(str(guidance.get("blocker_code") or ""), []))


def disposition_target(company: dict[str, Any]) -> dict[str, Any]:
    guidance = company.get("action_guidance") if isinstance(company.get("action_guidance"), dict) else {}
    review = company.get("review_coverage") if isinstance(company.get("review_coverage"), dict) else {}
    manual = review.get("manual_decision") if isinstance(review.get("manual_decision"), dict) else {}
    drift = company.get("drift") if isinstance(company.get("drift"), dict) else {}
    return {
        "ticker": str(company.get("ticker") or "").upper(),
        "blocker_code": str(guidance.get("blocker_code") or ""),
        "canonical_report_sha256": company.get("canonical_report_sha256") or None,
        "manual_review_source_fingerprint_sha256": company.get(
            "manual_review_source_fingerprint_sha256"
        ) or None,
        "current_formal_drift_trigger_fingerprint": manual.get(
            "current_formal_drift_trigger_fingerprint"
        ) or None,
        "formal_drift_review": {
            "direction": drift.get("direction") or None,
            "severity": drift.get("severity") or None,
            "last_checked": drift.get("last_checked") or None,
            "source": drift.get("source") or None,
        },
    }


def fingerprint_for_target(target: dict[str, Any]) -> str:
    encoded = json.dumps(
        target,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def target_fingerprint(company: dict[str, Any]) -> str:
    projected = company.get("manual_disposition")
    if isinstance(projected, dict):
        existing = str(projected.get("disposition_target_fingerprint") or "")
        if len(existing) == 64 and all(character in "0123456789abcdef" for character in existing):
            return existing
    return fingerprint_for_target(disposition_target(company))


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DispositionError("disposition authority must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise DispositionError("unsupported disposition authority schema")
    if payload.get("artifact_role") != "runtime_human_disposition_authority":
        raise DispositionError("invalid disposition authority role")
    records = payload.get("records")
    if not isinstance(records, list):
        raise DispositionError("disposition records must be a list")
    seen: set[tuple[str, str]] = set()
    for record in records:
        if not isinstance(record, dict):
            raise DispositionError("disposition record must be an object")
        ticker = str(record.get("ticker") or "").upper()
        fingerprint = str(record.get("disposition_target_fingerprint") or "")
        selected = str(record.get("selected_disposition") or "")
        if not ticker or not fingerprint or len(fingerprint) != 64:
            raise DispositionError("disposition record identity is invalid")
        if selected not in ALL_DISPOSITIONS:
            raise DispositionError("selected disposition is invalid")
        if not str(record.get("selected_at") or ""):
            raise DispositionError("selected_at is required")
        if record.get("selected_by") != "user" or record.get("source") != "dashboard_explicit_user_action":
            raise DispositionError("disposition actor or source is invalid")
        if record.get("effect_code") != DISPOSITION_EFFECT_CODES[selected]:
            raise DispositionError("disposition effect code is invalid")
        target = record.get("target")
        if not isinstance(target, dict) or fingerprint_for_target(target) != fingerprint:
            raise DispositionError("disposition target does not match its fingerprint")
        if str(target.get("ticker") or "").upper() != ticker:
            raise DispositionError("disposition target ticker does not match record ticker")
        key = (ticker, fingerprint)
        if key in seen:
            raise DispositionError("duplicate disposition record")
        seen.add(key)
    return payload


def load(path: Path | None, *, strict: bool = True) -> dict[str, Any]:
    if path is None or not path.is_file():
        return empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return validate_payload(payload)
    except (OSError, json.JSONDecodeError, DispositionError):
        if strict:
            raise
        return empty_payload()


def current_record(
    payload: dict[str, Any] | None,
    ticker: str,
    fingerprint: str,
) -> dict[str, Any] | None:
    for record in (payload or {}).get("records", []):
        if not isinstance(record, dict):
            continue
        if (
            str(record.get("ticker") or "").upper() == ticker.upper()
            and record.get("disposition_target_fingerprint") == fingerprint
        ):
            return record
    return None


def project_company(
    company: dict[str, Any], payload: dict[str, Any] | None
) -> dict[str, Any]:
    """Attach exact-fingerprint options and apply a matching human route."""
    result = copy.deepcopy(company)
    options = allowed_dispositions(result)
    fingerprint = target_fingerprint(result) if options else None
    record = current_record(payload, str(result.get("ticker") or ""), fingerprint or "")
    result["manual_disposition"] = {
        "allowed_options": options,
        "disposition_target_fingerprint": fingerprint,
        "selected_disposition": record.get("selected_disposition") if record else None,
        "selected_at": record.get("selected_at") if record else None,
        "status": "current" if record else "none",
    }
    if not record:
        return result

    selected = record["selected_disposition"]
    guidance = dict(result.get("action_guidance") or {})
    if selected == "keep_watch":
        guidance.update({
            "blocker_code": "user_selected_keep_watch",
            "blocker_text": "已记录人工决定：继续观察",
            "next_action_code": "continue_monitoring",
            "next_action_text": "无需操作，系统继续观察",
            "recommended_skill": [],
            "recommended_skill_reason": "当前任务已由投资者选择继续观察",
            "priority": "none",
            "requires_user_action": False,
            "completion_target": "仅在证据、报告基线或正式 Drift 触发发生变化时重新打开",
        })
        result["next_action"] = "keep_watch"
    elif selected == "redo_research":
        guidance.update({
            "blocker_code": "user_requested_research_refresh",
            "blocker_text": "已记录人工决定：重做研究",
            "next_action_code": "redo_investment_research",
            "next_action_text": "按需启动新的完整投资研究",
            "recommended_skill": ["investment-research"],
            "recommended_skill_reason": "投资者已明确选择重做研究；系统不会自动生成报告",
            "priority": "normal",
            "requires_user_action": True,
            "completion_target": "由投资者手动启动研究并审核新报告",
        })
    elif selected == "formal_drift":
        guidance.update({
            "blocker_code": "user_requested_formal_drift",
            "blocker_text": "已记录人工决定：执行正式投资逻辑漂移复核",
            "next_action_code": "review_investment_thesis",
            "next_action_text": "按需启动正式投资逻辑漂移复核",
            "recommended_skill": ["thesis-drift"],
            "recommended_skill_reason": "投资者已明确选择正式 Drift；系统不会自动运行模型",
            "priority": "normal",
            "requires_user_action": True,
            "completion_target": "由投资者手动启动 thesis-drift 并审核结果",
        })
        result["next_action"] = "run_drift"
    elif selected == "archive_drop":
        guidance.update({
            "blocker_code": "user_requested_archive",
            "blocker_text": "已记录人工决定：停止重点跟踪",
            "next_action_code": "archive_from_focus",
            "next_action_text": "无需继续处理当前提醒",
            "recommended_skill": [],
            "recommended_skill_reason": "仅停止重点跟踪；研究、Rule、持仓和生命周期均未改变",
            "priority": "none",
            "requires_user_action": False,
            "completion_target": "保留全部研究资料，未来出现新 fingerprint 时可重新进入队列",
        })
        result["next_action"] = "keep_watch"
    result["action_guidance"] = guidance
    result["needs_attention"] = guidance.get("requires_user_action") is True
    return result


class DispositionStore:
    """Atomic, process-safe runtime authority store."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.thread_lock = threading.Lock()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.thread_lock, self.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def payload(self) -> dict[str, Any]:
        return load(self.path, strict=True)

    def save(
        self,
        *,
        current_company: dict[str, Any],
        selected_disposition: str,
        submitted_fingerprint: str,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        options = allowed_dispositions(current_company)
        current_fingerprint = target_fingerprint(current_company) if options else ""
        if submitted_fingerprint != current_fingerprint:
            raise DispositionConflict("任务状态已经变化，请刷新后重新确认。")
        if selected_disposition not in options:
            raise DispositionError("该处置不适用于当前任务。")
        ticker = str(current_company.get("ticker") or "").upper()
        with self._locked():
            payload = load(self.path, strict=True)
            existing = current_record(payload, ticker, current_fingerprint)
            if existing:
                if existing.get("selected_disposition") != selected_disposition:
                    raise DispositionConflict("该任务已经记录了不同处置，不能静默覆盖。")
                return "noop", existing, payload
            record = {
                "ticker": ticker,
                "selected_disposition": selected_disposition,
                "disposition_target_fingerprint": current_fingerprint,
                "selected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "selected_by": "user",
                "source": "dashboard_explicit_user_action",
                "effect_code": DISPOSITION_EFFECT_CODES[selected_disposition],
                "target": disposition_target(current_company),
            }
            payload["records"].append(record)
            payload["records"].sort(
                key=lambda item: (
                    str(item.get("ticker") or ""),
                    str(item.get("disposition_target_fingerprint") or ""),
                )
            )
            validate_payload(payload)
            temporary = self.path.with_suffix(self.path.suffix + f".{os.getpid()}.tmp")
            try:
                temporary.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, self.path)
            finally:
                if temporary.exists():
                    temporary.unlink()
            return "saved", record, payload
