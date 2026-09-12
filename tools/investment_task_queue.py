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
import investment_tasks
import quote_quality


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = Path("data/investment-dashboard/company_state.json")
DEFAULT_DRIFT = Path("data/investment-dashboard/drift_states.json")
DEFAULT_BUY_THESES = Path("data/investment-dashboard/original_buy_theses.json")
DEFAULT_OUTPUT = Path("logs/investment-task-queue.json")
DEFAULT_PRODUCTION_URL = "http://vps.06070419.xyz/data"

PASSIVE_QUEUE_CLASSES = frozenset({"system_data_issue", "definition_gap", "waiting_evidence"})


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
    market: str | None = None,
) -> dict[str, Any]:
    queried_at = datetime.now().astimezone()
    companies = [c for c in state_payload.get("companies", [])
                 if isinstance(c, dict) and (not market or c.get("market") == market)]
    tickers = {str(c["ticker"]).upper() for c in companies
               if c.get("ticker") and c.get("market") in {"A股", "港股"}}
    quotes = (quote_payload or {}).get("quotes") or []
    if isinstance(quotes, dict):
        quotes = [{"ticker": ticker, **value} for ticker, value in quotes.items() if isinstance(value, dict)]
    quotes_by_ticker = quote_quality.with_quote_metadata({
        **(quote_payload or {}), "quotes": quotes,
        "source_status": (quote_payload or {}).get("source_status") or (quote_payload or {}).get("status"),
    })
    scoped_quotes = {ticker: row for ticker, row in quotes_by_ticker.items() if ticker in tickers}
    # Re-evaluate even annotated snapshots at query time: stored eligibility
    # expires, and legacy remote snapshots may not contain quality at all.
    usable = {ticker for ticker, row in scoped_quotes.items()
              if quote_quality.quote_quality(row, queried_at)["eligible"] is True}
    if quote_payload is None:
        completeness = "local_snapshot_missing" if source == "local" else "production_snapshot_missing"
    elif not tickers:
        completeness = "not_applicable"
    elif not usable:
        completeness = "unavailable"
    elif usable != tickers:
        completeness = "partial"
    else:
        completeness = "available"
    evidence_dates = [
        (company.get("event_radar") or {}).get("data_cutoff")
        for company in companies if isinstance(company, dict)
    ]
    return {
        "source": source,
        "source_location": source_location,
        "source_sha": state_payload.get("source_sha"),
        "checkout_sha": source_sha if source == "local" else None,
        "reported_deploy_sha": source_sha if source == "production" else None,
        "state_generated_at": state_payload.get("generated_at"),
        "evaluation_at": state_payload.get("evaluated_at"),
        "queried_at": queried_at.isoformat(timespec="seconds"),
        "market": market or "all",
        "quote_data_cutoff": _latest_date([q.get("data_cutoff") for q in scoped_quotes.values()]),
        "evidence_data_cutoff": _latest_date(evidence_dates),
        "quote_coverage": {"expected": len(tickers), "usable": len(usable)},
        "data_completeness": {
            "company_state": "available",
            "quotes": completeness,
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
            "source_identity": list((drift_record or drift).get("facts_sources") or []),
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
            "date": evaluation.get("evidence_date"),
            "evaluated_at": evaluation.get("evaluated_at"),
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
        if disposition_payload is not None:
            company = investment_dispositions.project_company(company, disposition_payload)
        guidance = company.get("action_guidance")
        if not isinstance(guidance, dict):
            continue
        ticker = str(company.get("ticker") or "").upper()
        blocker = str(guidance.get("blocker_code") or "unknown")
        task = investment_tasks.classify(guidance)
        task_class = task["task_class"]
        if guidance.get("requires_user_action") is not True and task_class not in PASSIVE_QUEUE_CLASSES:
            continue
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
            **task,
            "allowed_user_dispositions": options,
            "disposition_target_fingerprint": disposition_fingerprint,
            "current_disposition": current_disposition,
            "action_guidance": guidance,
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
    parser.add_argument("--investment-dispositions", type=Path, default=None,
                        help="Optional runtime disposition authority applied before task classification")
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
        before = fetch_json(f"{base}/automation_status.json")
        state_payload = fetch_json(f"{base}/company_state.json")
        drift_payload = None
        thesis_payload = fetch_json(f"{base}/original_buy_theses.json")
        quote_payload = fetch_json(f"{base}/quotes/latest.json")
        alerts_payload = fetch_json(f"{base}/post_buy_alerts.json")
        automation = fetch_json(f"{base}/automation_status.json")
        source_sha = ((automation.get("jobs") or {}).get("deploy") or {}).get("source_sha")
        before_sha = ((before.get("jobs") or {}).get("deploy") or {}).get("source_sha")
        if before_sha != source_sha or (state_payload.get("source_sha") and state_payload["source_sha"] != source_sha):
            raise ValueError("production release changed during query; retry without mixing versions")
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
        disposition_payload=(investment_dispositions.load(resolve(args.investment_dispositions))
                             if args.investment_dispositions is not None else None),
        market=args.market,
    )
    result["source_metadata"] = source_metadata(
        state_payload,
        source=args.source,
        source_location=source_location,
        source_sha=source_sha,
        quote_payload=quote_payload,
        alerts_payload=alerts_payload,
        market=args.market,
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
