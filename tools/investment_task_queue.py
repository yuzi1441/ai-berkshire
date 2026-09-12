#!/usr/bin/env python3
"""Build audit-only evidence packets for current human investment tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import investment_dispositions


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = Path("data/investment-dashboard/company_state.json")
DEFAULT_DRIFT = Path("data/investment-dashboard/drift_states.json")
DEFAULT_BUY_THESES = Path("data/investment-dashboard/original_buy_theses.json")
DEFAULT_OUTPUT = Path("logs/investment-task-queue.json")
DEFAULT_PRODUCTION_URL = "http://vps.06070419.xyz/data"

WORKFLOW_STATUS = {
    "reviewed_thesis_weakened": "READY_FOR_USER_DISPOSITION",
    "confirmed_redline": "READY_FOR_THESIS_DRIFT",
    "holding_review_due": "READY_FOR_THESIS_TRACKER",
}

TASK_CLASSES = {
    "reviewed_thesis_weakened": "human_decision",
    "covered_redline_requires_decision": "human_decision",
    "review_result_requires_decision": "human_decision",
    "confirmed_redline": "research_now",
    "thesis_review_required": "research_now",
    "holding_material_event": "research_now",
    "holding_review_due": "research_now",
    "pre_buy_checklist_missing": "research_now",
    "market_data_unavailable": "system_data_issue",
    "financial_definition_missing": "definition_gap",
    "evidence_not_available": "waiting_evidence",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_json(url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AI-Berkshire-task-query/1.0", "Cache-Control": "no-cache"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValueError(f"production data unavailable: {url}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {url}")
    return value


def local_git_sha(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=False, capture_output=True, text=True
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _latest_date(values: list[Any]) -> str | None:
    dates = sorted(str(value)[:10] for value in values if str(value or "")[:10])
    return dates[-1] if dates else None


def source_metadata(
    state_payload: dict[str, Any],
    *,
    source: str,
    source_location: str,
    source_sha: str | None,
    quote_payload: dict[str, Any] | None,
    alerts_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    companies = state_payload.get("companies") or []
    evidence_dates = [
        (company.get("event_radar") or {}).get("data_cutoff")
        for company in companies if isinstance(company, dict)
    ]
    return {
        "source": source,
        "source_location": source_location,
        "source_sha": source_sha,
        "state_generated_at": state_payload.get("generated_at"),
        "evaluation_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "quote_data_cutoff": (quote_payload or {}).get("data_cutoff"),
        "evidence_data_cutoff": _latest_date(evidence_dates),
        "data_completeness": {
            "company_state": "available",
            "quotes": "available" if quote_payload is not None else "local_snapshot_missing" if source == "local" else "production_snapshot_missing",
            "post_buy_alerts": "available" if alerts_payload is not None else "local_snapshot_missing" if source == "local" else "production_snapshot_missing",
        },
    }


def _drift_by_ticker(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    values = (payload or {}).get("companies", {})
    if isinstance(values, dict):
        return {str(key).upper(): value for key, value in values.items() if isinstance(value, dict)}
    return {}


def _original_thesis_ref(
    ticker: str, payload: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    position_id = (payload.get("active_position_ids") or {}).get(ticker)
    cycle = (payload.get("cycles") or {}).get(position_id)
    if not position_id or not isinstance(cycle, dict):
        return None
    return {
        "position_id": position_id,
        "source_report": cycle.get("source_report"),
        "source_hash": cycle.get("source_hash"),
        "captured_at": cycle.get("captured_at"),
    }


def _evidence_items(
    company: dict[str, Any], drift_record: dict[str, Any] | None
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    drift = company.get("drift") if isinstance(company.get("drift"), dict) else {}
    if drift.get("summary"):
        items.append({
            "type": "formal_drift_result",
            "date": drift.get("last_checked"),
            "source": drift.get("source") or "drift_states",
            "source_identity": list((drift_record or {}).get("facts_sources") or []),
            "concise_fact": drift.get("summary"),
            "result": drift.get("direction"),
            "severity": drift.get("severity"),
        })

    rules = (company.get("decision_rules") or {}).get("rules", [])
    for rule in rules if isinstance(rules, list) else []:
        if not isinstance(rule, dict) or rule.get("status") != "triggered":
            continue
        evaluation = rule.get("evaluation") if isinstance(rule.get("evaluation"), dict) else {}
        items.append({
            "type": "confirmed_rule_evaluation",
            "date": evaluation.get("evidence_date") or evaluation.get("evaluated_at"),
            "source": evaluation.get("evidence_source") or "rule_evaluations",
            "source_identity": rule.get("rule_id"),
            "concise_fact": evaluation.get("review_reason") or rule.get("condition"),
            "result": rule.get("status"),
            "evidence_fingerprint": evaluation.get("evidence_fingerprint"),
        })

    tracking = company.get("post_buy_tracking")
    alerts = tracking.get("alerts", []) if isinstance(tracking, dict) else []
    for alert in alerts if isinstance(alerts, list) else []:
        if not isinstance(alert, dict):
            continue
        items.append({
            "type": "post_buy_alert",
            "date": alert.get("due_date") or alert.get("event_date"),
            "source": "post_buy_alerts",
            "source_identity": alert.get("kind"),
            "concise_fact": alert.get("detail") or alert.get("title"),
            "severity": alert.get("severity"),
        })
    return sorted(
        items,
        key=lambda item: (
            str(item.get("date") or ""),
            str(item.get("type") or ""),
            str(item.get("source_identity") or ""),
        ),
    )


def build_task_queue(
    state_payload: dict[str, Any],
    *,
    drift_payload: dict[str, Any] | None = None,
    original_buy_theses: dict[str, Any] | None = None,
    disposition_payload: dict[str, Any] | None = None,
    market: str | None = None,
) -> dict[str, Any]:
    companies = state_payload.get("companies")
    if not isinstance(companies, list):
        raise ValueError("company_state.companies must be a list")
    drift_records = _drift_by_ticker(drift_payload)
    packets: list[dict[str, Any]] = []
    for company in companies:
        if not isinstance(company, dict):
            continue
        if market and company.get("market") != market:
            continue
        guidance = company.get("action_guidance")
        if not isinstance(guidance, dict) or guidance.get("requires_user_action") is not True:
            continue
        ticker = str(company.get("ticker") or "").upper()
        blocker = str(guidance.get("blocker_code") or "unknown")
        manual = ((company.get("review_coverage") or {}).get("manual_decision") or {})
        options = investment_dispositions.allowed_dispositions(company)
        disposition_fingerprint = (
            investment_dispositions.target_fingerprint(company) if options else None
        )
        current_disposition = investment_dispositions.current_record(
            disposition_payload,
            ticker,
            disposition_fingerprint or "",
        )
        packet = {
            "ticker": ticker,
            "company": company.get("company"),
            "market": company.get("market"),
            "lifecycle": company.get("lifecycle"),
            "next_action": company.get("next_action"),
            "why_actionable": guidance.get("recommended_skill_reason"),
            "blocker": {
                "code": blocker,
                "text": guidance.get("blocker_text"),
            },
            "recommended_skill": list(guidance.get("recommended_skill") or []),
            "completion_target": guidance.get("completion_target"),
            "workflow_status": WORKFLOW_STATUS.get(blocker, "READY_FOR_USER_REVIEW"),
            "task_class": TASK_CLASSES.get(blocker, "human_review"),
            "allowed_user_dispositions": options,
            "disposition_target_fingerprint": disposition_fingerprint,
            "current_disposition": current_disposition,
            "current_evidence": _evidence_items(company, drift_records.get(ticker)),
            "authority_references": {
                "canonical_report": company.get("canonical_report"),
                "canonical_report_sha256": company.get("canonical_report_sha256"),
                "manual_review_source_fingerprint_sha256": company.get(
                    "manual_review_source_fingerprint_sha256"
                ),
                "formal_drift_trigger_fingerprint": manual.get(
                    "current_formal_drift_trigger_fingerprint"
                ),
                "original_buy_thesis": _original_thesis_ref(ticker, original_buy_theses),
            },
        }
        packets.append(packet)
    packets.sort(key=lambda item: (str(item.get("ticker")), str(item.get("company"))))
    blocker_counts: dict[str, int] = {}
    for packet in packets:
        code = str((packet.get("blocker") or {}).get("code") or "unknown")
        blocker_counts[code] = blocker_counts.get(code, 0) + 1
    return {
        "schema_version": 1,
        "artifact_role": "derived_audit_only",
        "investment_authority": False,
        "task_count": len(packets),
        "market": market or "all",
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "tasks": packets,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--drift", type=Path, default=DEFAULT_DRIFT)
    parser.add_argument("--original-buy-theses", type=Path, default=DEFAULT_BUY_THESES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", choices=("local", "production"), default="local")
    parser.add_argument("--market", default=None, help="Exact market label, for example A股")
    parser.add_argument("--production-url", default=DEFAULT_PRODUCTION_URL)
    args = parser.parse_args()
    root = args.repo_root.resolve()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    state_path = resolve(args.state)
    drift_path = resolve(args.drift)
    thesis_path = resolve(args.original_buy_theses)
    output_path = resolve(args.output)
    if args.source == "production":
        base = args.production_url.rstrip("/")
        state_payload = fetch_json(f"{base}/company_state.json")
        drift_payload = None
        thesis_payload = fetch_json(f"{base}/original_buy_theses.json")
        quote_payload = fetch_json(f"{base}/quotes/latest.json")
        alerts_payload = fetch_json(f"{base}/post_buy_alerts.json")
        automation = fetch_json(f"{base}/automation_status.json")
        source_sha = ((automation.get("jobs") or {}).get("deploy") or {}).get("source_sha")
        source_location = base
    else:
        state_payload = load_json(state_path)
        drift_payload = load_json(drift_path) if drift_path.is_file() else None
        thesis_payload = load_json(thesis_path) if thesis_path.is_file() else None
        quote_path = root / "data/investment-dashboard/quotes/latest.json"
        alerts_path = root / "data/investment-dashboard/post_buy_alerts.json"
        quote_payload = load_json(quote_path) if quote_path.is_file() else None
        alerts_payload = load_json(alerts_path) if alerts_path.is_file() else None
        source_sha = local_git_sha(root)
        source_location = str(root)
    result = build_task_queue(
        state_payload,
        drift_payload=drift_payload,
        original_buy_theses=thesis_payload,
        market=args.market,
    )
    result["source_metadata"] = source_metadata(
        state_payload,
        source=args.source,
        source_location=source_location,
        source_sha=source_sha,
        quote_payload=quote_payload,
        alerts_payload=alerts_payload,
    )
    result["sources"] = {
        "company_state": ({"path": str(state_path), "sha256": file_sha256(state_path)} if args.source == "local" else {"url": f"{source_location}/company_state.json"}),
        "drift_states": (
            {"path": str(drift_path), "sha256": file_sha256(drift_path)}
            if args.source == "local" and drift_path.is_file() else None
        ),
        "original_buy_theses": (
            {"path": str(thesis_path), "sha256": file_sha256(thesis_path)}
            if args.source == "local" and thesis_path.is_file() else {"url": f"{source_location}/original_buy_theses.json"} if args.source == "production" else None
        ),
    }
    write_json(output_path, result)
    print(json.dumps({
        "task_count": result["task_count"],
        "blocker_counts": result["blocker_counts"],
    }, ensure_ascii=False, sort_keys=True))
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
