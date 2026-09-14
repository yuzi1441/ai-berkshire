#!/usr/bin/env python3
"""Deterministic transaction boundary for local daily investment reviews.

This module prepares compact A-share evidence packets and validates artifacts
written by the currently running Codex/ChatGPT model.  It never calls a model
API and never changes investment authority records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import io
import tarfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MARKET = "A股"
SKILL_NAME = "daily-investment-review"
CONTRACT_VERSION = "1.0.0"
INPUT_SCHEMA_VERSION = 1
REVIEW_SCHEMA_VERSION = 1
PUBLISHED_SCHEMA_VERSION = 1
MAX_REUSE_DAYS = 7

PUBLISHED_ROOT = Path("data/local-daily-review/published")
PUBLISHED_POINTER = PUBLISHED_ROOT / "latest.json"
AUTHORITY_PATHS = (
    "data/investment-dashboard/current_reports.json",
    "data/investment-dashboard/decision_rules.json",
    "data/investment-dashboard/original_buy_theses.json",
    "data/investment-dashboard/holding_research_reviews.json",
    "data/investment-dashboard/drift_states.json",
    "data/investment-dashboard/light_thesis_signals.json",
    "data/investment-dashboard/report_judgments",
)
OPPORTUNITY_STATES = {"当前机会", "临近机会", "暂不构成当前机会", "证据不足"}
CONFIDENCE = {"high", "medium", "low"}
VERIFICATION_DECISIONS = {"confirm", "downgrade", "reject"}


class LocalReviewError(RuntimeError):
    """Raised when a local review transaction cannot be trusted."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LocalReviewError(f"invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise LocalReviewError(f"expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def value_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(value: Any, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def indexed(rows: Any) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("ticker") or row.get("company_id") or "").upper(): row
        for row in rows if isinstance(row, dict) and (row.get("ticker") or row.get("company_id"))
    } if isinstance(rows, list) else {}


def source_sha(repo_root: Path) -> str:
    marker = repo_root / ".source-sha"
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip()
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, check=False, capture_output=True, text=True
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def normalize_headline(value: Any) -> str:
    text = clean_text(value, 500).casefold()
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return re.sub(r"(?:[-_—|].*?(?:新浪|搜狐|证券之星|东方财富|腾讯|网易).*)$", "", text)


def raw_news_items(company: dict[str, Any]) -> list[dict[str, Any]]:
    sentiment = company.get("news_sentiment") if isinstance(company.get("news_sentiment"), dict) else {}
    rows = sentiment.get("captured_items") or sentiment.get("items") or []
    return [dict(row) for row in rows if isinstance(row, dict) and row.get("title")]


def cluster_news(company: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    """Collapse deterministic duplicate headlines before semantic review."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in raw_news_items(company):
        published = clean_text(item.get("published_at"), 40)[:10]
        identity = normalize_headline(item.get("title")) or clean_text(item.get("source_id"), 200)
        key = f"{ticker}|{published}|{identity}"
        groups.setdefault(key, []).append(item)
    tier_rank = {"A": 0, "B": 1, "C": 2, "D": 3}
    clusters: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        rows.sort(key=lambda row: (tier_rank.get(str(row.get("source_tier")), 9), str(row.get("source_id") or "")))
        primary = rows[0]
        event_id = "event:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        clusters.append({
            "event_id": event_id,
            "title": clean_text(primary.get("title"), 500),
            "summary": clean_text(primary.get("summary"), 900),
            "published_at": primary.get("published_at"),
            "source_tier": primary.get("source_tier"),
            "source_ids": sorted({clean_text(row.get("source_id"), 240) for row in rows if row.get("source_id")}),
            "publishers": sorted({clean_text(row.get("publisher"), 120) for row in rows if row.get("publisher")}),
            "urls": sorted({str(row.get("url")) for row in rows if row.get("url")}),
            "duplicate_count": len(rows),
        })
    return clusters


def cluster_industry_news(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Cluster each industry's news once instead of once per constituent."""
    details = raw.get("industry_sentiments")
    if not isinstance(details, dict):
        return []
    clusters: list[dict[str, Any]] = []
    for industry, detail in sorted(details.items()):
        if not isinstance(detail, dict):
            continue
        sentiment = detail.get("sentiment") if isinstance(detail.get("sentiment"), dict) else {}
        rows = sentiment.get("captured_items") or sentiment.get("items") or []
        synthetic = {"news_sentiment": {"captured_items": rows}}
        for event in cluster_news(synthetic, f"industry:{industry}"):
            event["industry"] = industry
            event["event_id"] = event["event_id"].replace("event:", "industry-event:", 1)
            clusters.append(event)
    return clusters


def prior_industry_event_reviews(repo_root: Path) -> list[dict[str, Any]]:
    payload = load_published_component(repo_root, "sentiment") or {}
    details = payload.get("industry_sentiments")
    if not isinstance(details, dict):
        return []
    rows = []
    for detail in details.values():
        if isinstance(detail, dict):
            rows.extend(((detail.get("local_review") or {}).get("event_reviews") or []))
    return [dict(row) for row in rows if isinstance(row, dict) and row.get("event_id")]


def compact_decision(decision: dict[str, Any], state: dict[str, Any], quote: dict[str, Any],
                     daily: dict[str, Any], intraday: dict[str, Any], raw_company: dict[str, Any]) -> dict[str, Any]:
    ticker = str(decision.get("ticker") or "").upper()
    report_path = clean_text(decision.get("report_path"), 500)
    rules = ((state.get("decision_rules") or {}).get("rules") or []) if isinstance(state, dict) else []
    evidence_catalog = {
        "rule_ids": sorted({str(item.get("rule_id")) for item in rules if isinstance(item, dict) and item.get("rule_id")}),
        "checklist_gates": sorted({str(item.get("name")) for item in ((decision.get("checklist") or {}).get("gates") or []) if isinstance(item, dict) and item.get("name")}),
        "report_paths": [report_path] if report_path else [],
    }
    clusters = cluster_news(raw_company, ticker)
    evidence_catalog["event_ids"] = [item["event_id"] for item in clusters]
    canonical = {
        "report": report_path,
        "report_sha256": decision.get("current_report_sha256") or state.get("canonical_report_sha256"),
        "cutoff": decision.get("data_cutoff"),
        "primary_judgment": decision.get("primary_judgment"),
        "execution_policy": decision.get("execution_policy"),
    }
    packet = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "skill_contract_version": CONTRACT_VERSION,
        "company": decision.get("company"),
        "ticker": ticker,
        "market": decision.get("market"),
        "canonical": canonical,
        "price": quote,
        "daily_technical": daily or decision.get("technical_analysis") or {},
        "intraday_30m": intraday,
        "checklist": decision.get("checklist") or {},
        "drift": state.get("drift") or {},
        "current_decision_state": {
            key: state.get(key) for key in (
                "lifecycle", "next_action", "action_guidance", "price_opportunities",
                "condition_opportunities", "warning",
            )
        },
        "sentiment_raw_evidence": {
            "event_clusters": clusters,
            "industry": raw_company.get("industry"),
            "industry_raw": raw_company.get("industry_sentiment"),
            "market_raw": raw_company.get("market_sentiment"),
            "crowding": raw_company.get("crowding"),
        },
        "evidence_catalog": evidence_catalog,
    }
    def stable_material(value: Any) -> Any:
        volatile = {"generated_at", "updated_at", "evaluated_at", "last_checked", "data_cutoff",
                    "requested_cutoff", "provider_timestamp", "checkpoint_at"}
        if isinstance(value, dict):
            return {key: stable_material(item) for key, item in sorted(value.items()) if key not in volatile}
        if isinstance(value, list):
            return [stable_material(item) for item in value]
        return value

    material = {
        "report_sha256": canonical.get("report_sha256"),
        "primary_judgment": canonical.get("primary_judgment"),
        "execution_policy": canonical.get("execution_policy"),
        "price_materiality": stable_material(state.get("price_opportunities") or []),
        "checklist": stable_material(packet["checklist"]),
        "daily_technical": stable_material(packet["daily_technical"]),
        # 30m is execution context and deliberately excluded from materiality.
        "formal_event_ids": [item["event_id"] for item in clusters if item.get("source_tier") in {"A", "B"}],
        "current_state": stable_material(packet["current_decision_state"]),
    }
    packet["materiality"] = {"snapshot": material, "fingerprint": value_sha256(material)}
    packet["input_sha256"] = value_sha256(packet)
    return packet


def load_published_component(repo_root: Path, component: str) -> dict[str, Any] | None:
    pointer_path = repo_root / PUBLISHED_POINTER
    if not pointer_path.is_file():
        return None
    pointer = read_json(pointer_path)
    entry = (pointer.get("components") or {}).get(component)
    if not isinstance(entry, dict) or not entry.get("path") or not entry.get("sha256"):
        raise LocalReviewError(f"published pointer missing component: {component}")
    path = (repo_root / str(entry["path"])).resolve()
    if not path.is_relative_to(repo_root.resolve()) or not path.is_file():
        raise LocalReviewError(f"published component missing/outside repository: {component}")
    if file_sha256(path) != entry["sha256"]:
        raise LocalReviewError(f"published component hash mismatch: {component}")
    return read_json(path)


def prior_scan_map(repo_root: Path) -> dict[str, dict[str, Any]]:
    payload = load_published_component(repo_root, "opportunity") or {}
    return indexed(payload.get("scans"))


def prior_sentiment_map(repo_root: Path) -> dict[str, dict[str, Any]]:
    payload = load_published_component(repo_root, "sentiment") or {}
    return indexed(payload.get("companies"))


def review_plan(packet: dict[str, Any], prior: dict[str, Any] | None, as_of: date, force: bool) -> dict[str, Any]:
    if force:
        return {"opportunity_action": "reevaluate", "reasons": ["force"]}
    if not prior or prior.get("skill_contract_version") != CONTRACT_VERSION:
        return {"opportunity_action": "reevaluate", "reasons": ["no_compatible_previous_review"]}
    previous_fingerprint = prior.get("material_trigger_fingerprint")
    if previous_fingerprint != packet["materiality"]["fingerprint"]:
        return {"opportunity_action": "reevaluate", "reasons": ["material_change"]}
    state = str(((prior.get("final") or {}).get("assessment") or {}).get("opportunity_state") or "")
    generated = clean_text(prior.get("last_model_evaluated_at") or prior.get("generated_at"), 40)
    try:
        generated_date = datetime.fromisoformat(generated.replace("Z", "+00:00")).date()
    except ValueError:
        return {"opportunity_action": "reevaluate", "reasons": ["previous_age_unknown"]}
    if state in {"当前机会", "临近机会"} and generated_date < as_of:
        return {"opportunity_action": "reevaluate", "reasons": ["current_or_near_daily_refresh"]}
    if as_of - generated_date > timedelta(days=MAX_REUSE_DAYS):
        return {"opportunity_action": "reevaluate", "reasons": ["maximum_reuse_age_exceeded"]}
    return {"opportunity_action": "reuse", "reasons": ["materiality_unchanged"]}


def prepare(repo_root: Path, output_root: Path, as_of: date, raw_sentiment_path: Path, *, force: bool = False,
            tickers: set[str] | None = None) -> dict[str, Any]:
    board = read_json(repo_root / "data/investment-dashboard/decision_board.json")
    state = read_json(repo_root / "data/investment-dashboard/company_state.json")
    quotes = read_json(repo_root / "data/investment-dashboard/quotes/latest.json")
    raw = read_json(raw_sentiment_path)
    daily_path = repo_root / "data/investment-dashboard/technical_daily_snapshot.json"
    intraday_path = repo_root / "data/investment-dashboard/intraday_technical.json"
    daily_payload = read_json(daily_path) if daily_path.is_file() else {"companies": []}
    intraday_payload = read_json(intraday_path) if intraday_path.is_file() else {"companies": []}

    decisions = [row for row in board.get("decisions", []) if isinstance(row, dict) and row.get("market") == MARKET]
    selected_tickers = {ticker.upper() for ticker in tickers} if tickers else None
    if selected_tickers is not None:
        available = {str(row.get("ticker") or "").upper() for row in decisions}
        missing = sorted(selected_tickers - available)
        if missing:
            raise LocalReviewError(f"requested A-share ticker not found: {', '.join(missing)}")
        decisions = [row for row in decisions if str(row.get("ticker") or "").upper() in selected_tickers]
    if not decisions:
        raise LocalReviewError("no A-share decisions")
    if raw.get("data_cutoff") != as_of.isoformat() or raw.get("retrieval_complete") is not True:
        raise LocalReviewError("raw sentiment is not complete for requested date")
    quote_cutoff = str(quotes.get("data_cutoff") or "")[:10]
    if quote_cutoff != as_of.isoformat():
        raise LocalReviewError(f"quote cutoff mismatch: {quote_cutoff} != {as_of.isoformat()}")

    state_by = indexed(state.get("companies"))
    quote_by = indexed(quotes.get("quotes"))
    raw_by = indexed(raw.get("companies"))
    daily_by = indexed(daily_payload.get("companies"))
    intraday_by = indexed(intraday_payload.get("companies"))
    prior_by = prior_scan_map(repo_root)
    prior_sentiment = prior_sentiment_map(repo_root)
    packets_dir = output_root / "packets"
    packet_entries = []
    plans = []
    for decision in sorted(decisions, key=lambda row: str(row.get("ticker") or "")):
        ticker = str(decision.get("ticker") or "").upper()
        if ticker not in state_by or ticker not in quote_by or ticker not in raw_by:
            raise LocalReviewError(f"incomplete deterministic input for {ticker}")
        packet = compact_decision(
            decision, state_by[ticker], quote_by[ticker], daily_by.get(ticker, {}),
            intraday_by.get(ticker, {}), raw_by[ticker],
        )
        packet["review_plan"] = review_plan(packet, prior_by.get(ticker), as_of, force)
        packet["previous_review"] = prior_by.get(ticker)
        previous_events = (((prior_sentiment.get(ticker) or {}).get("local_review") or {}).get("event_reviews") or [])
        current_event_ids = {item["event_id"] for item in packet["sentiment_raw_evidence"]["event_clusters"]}
        reusable_events = [] if force else [
            item for item in previous_events if isinstance(item, dict) and item.get("event_id") in current_event_ids
        ]
        packet["previous_sentiment_event_reviews"] = reusable_events
        packet["sentiment_review_plan"] = {
            "classify_event_ids": sorted(current_event_ids - {item["event_id"] for item in reusable_events}),
            "reuse_event_ids": sorted({item["event_id"] for item in reusable_events}),
        }
        packet["input_sha256"] = value_sha256({key: value for key, value in packet.items() if key != "input_sha256"})
        path = packets_dir / f"{ticker}.json"
        write_json(path, packet)
        packet_entries.append({"ticker": ticker, "path": f"packets/{ticker}.json", "sha256": file_sha256(path), "input_sha256": packet["input_sha256"]})
        plans.append(packet["review_plan"]["opportunity_action"])

    selected_industries = {
        str(raw_by[str(decision.get("ticker") or "").upper()].get("industry") or "")
        for decision in decisions
    } - {""}
    industry_events = [
        item for item in cluster_industry_news(raw) if item.get("industry") in selected_industries
    ]
    industry_event_ids = {item["event_id"] for item in industry_events}
    prior_industry = [] if force else [
        item for item in prior_industry_event_reviews(repo_root) if item.get("event_id") in industry_event_ids
    ]
    shared = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "skill_contract_version": CONTRACT_VERSION,
        "market": MARKET,
        "sentiment_raw_evidence": {"event_clusters": industry_events},
        "previous_sentiment_event_reviews": prior_industry,
        "sentiment_review_plan": {
            "classify_event_ids": sorted(industry_event_ids - {item["event_id"] for item in prior_industry}),
            "reuse_event_ids": sorted({item["event_id"] for item in prior_industry}),
        },
    }
    shared["input_sha256"] = value_sha256(shared)
    shared_path = output_root / "shared.json"
    write_json(shared_path, shared)

    manifest = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "status": "awaiting_local_review",
        "date": as_of.isoformat(),
        "source_sha": source_sha(repo_root),
        "market": MARKET,
        "quotes_ready": True,
        "news_ready": True,
        "technical_ready": len(daily_by) >= len(decisions),
        "canonical_ready": len(state_by) >= len(decisions),
        "company_count": len(packet_entries),
        "review_scope": "partial_dry_run" if selected_tickers is not None else "full_a_share",
        "publication_eligible": selected_tickers is None,
        "reevaluate_count": plans.count("reevaluate"),
        "reuse_count": plans.count("reuse"),
        "external_llm_required": False,
        "shared": {"path": "shared.json", "sha256": file_sha256(shared_path),
                   "input_sha256": shared["input_sha256"], "industry_event_count": len(industry_events)},
        "packets": packet_entries,
    }
    if not manifest["technical_ready"]:
        raise LocalReviewError("daily technical input incomplete")
    manifest["manifest_sha256"] = value_sha256(manifest)
    write_json(output_root / "manifest.json", manifest)
    return manifest


def validate_input(input_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = read_json(input_root / "manifest.json")
    expected_hash = manifest.get("manifest_sha256")
    actual_hash = value_sha256({key: value for key, value in manifest.items() if key != "manifest_sha256"})
    if expected_hash != actual_hash or manifest.get("status") != "awaiting_local_review":
        raise LocalReviewError("input manifest invalid")
    if manifest.get("market") != MARKET or manifest.get("external_llm_required") is not False:
        raise LocalReviewError("input scope/provider boundary invalid")
    shared_entry = manifest.get("shared")
    if not isinstance(shared_entry, dict):
        raise LocalReviewError("shared industry packet proof missing")
    shared_path = (input_root / str(shared_entry.get("path") or "")).resolve()
    if not shared_path.is_relative_to(input_root.resolve()) or not shared_path.is_file():
        raise LocalReviewError("shared industry packet path invalid")
    if file_sha256(shared_path) != shared_entry.get("sha256"):
        raise LocalReviewError("shared industry packet hash failed")
    shared = read_json(shared_path)
    if shared.get("input_sha256") != shared_entry.get("input_sha256"):
        raise LocalReviewError("shared industry input hash failed")
    packets: dict[str, dict[str, Any]] = {}
    for entry in manifest.get("packets", []):
        if not isinstance(entry, dict):
            raise LocalReviewError("invalid packet entry")
        path = (input_root / str(entry.get("path") or "")).resolve()
        if not path.is_relative_to(input_root.resolve()) or file_sha256(path) != entry.get("sha256"):
            raise LocalReviewError(f"packet proof failed: {entry.get('ticker')}")
        packet = read_json(path)
        if packet.get("input_sha256") != entry.get("input_sha256"):
            raise LocalReviewError(f"packet input hash failed: {entry.get('ticker')}")
        packets[str(entry["ticker"]).upper()] = packet
    if len(packets) != manifest.get("company_count"):
        raise LocalReviewError("packet count mismatch")
    return manifest, packets


def require_number(value: Any, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= float(value) <= high:
        raise LocalReviewError(f"{label} must be between {low} and {high}")
    return float(value)


def validate_evidence_refs(refs: Any, packet: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(refs, list) or not refs:
        raise LocalReviewError(f"{packet['ticker']} opportunity requires evidence_refs")
    catalog = packet["evidence_catalog"]
    result = []
    for ref in refs:
        if not isinstance(ref, dict) or not clean_text(ref.get("reason"), 500):
            raise LocalReviewError(f"{packet['ticker']} invalid evidence ref")
        kind = ref.get("type")
        valid = (
            kind in {"formal_news", "event_cluster"} and ref.get("id") in catalog["event_ids"]
            or kind in {"price_rule", "decision_rule"} and ref.get("rule_id") in catalog["rule_ids"]
            or kind == "checklist" and ref.get("gate") in catalog["checklist_gates"]
            or kind == "report" and ref.get("report_path") in catalog["report_paths"]
        )
        if not valid:
            raise LocalReviewError(f"{packet['ticker']} invented evidence reference: {ref}")
        result.append(dict(ref))
    return result


def validate_assessment(value: Any, packet: dict[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("opportunity_state") not in OPPORTUNITY_STATES:
        raise LocalReviewError(f"{packet['ticker']} invalid {label} opportunity state")
    for field in ("why_now", "satisfied_conditions", "unmet_conditions", "supporting_evidence", "risks_or_counterevidence"):
        if field not in value:
            raise LocalReviewError(f"{packet['ticker']} {label} missing {field}")
    if value.get("confidence") not in CONFIDENCE:
        raise LocalReviewError(f"{packet['ticker']} invalid {label} confidence")
    result = dict(value)
    result["evidence_refs"] = validate_evidence_refs(value.get("evidence_refs"), packet)
    return result


def verification_required(event: dict[str, Any], review: dict[str, Any]) -> bool:
    return bool(
        event.get("source_tier") in {"A", "B"}
        and (
            review.get("impact", 0) >= 4
            or review.get("confidence", 1) < 0.6
            or abs(review.get("direction", 0)) >= 0.75
            or review.get("relevance", 1) < 0.6
        )
    )


def validated_event_reviews(packet: dict[str, Any], review: dict[str, Any]) -> list[dict[str, Any]]:
    events = {row["event_id"]: row for row in packet["sentiment_raw_evidence"]["event_clusters"]}
    rows = review.get("sentiment", {}).get("events") if isinstance(review.get("sentiment"), dict) else None
    if not isinstance(rows, list):
        raise LocalReviewError(f"{packet['ticker']} sentiment events missing")
    previous = {
        row.get("event_id"): row for row in packet.get("previous_sentiment_event_reviews", [])
        if isinstance(row, dict) and row.get("event_id") in events
    }
    supplied = {row.get("event_id"): row for row in rows if isinstance(row, dict) and row.get("event_id")}
    if set(supplied) & set(previous):
        # Explicit reclassification is allowed only when the packet requests it.
        unexpected = (set(supplied) & set(previous)) - set(packet["sentiment_review_plan"]["classify_event_ids"])
        if unexpected:
            raise LocalReviewError(f"{packet['ticker']} reclassified cached events unexpectedly")
    combined = {**previous, **supplied}
    if set(combined) != set(events):
        raise LocalReviewError(f"{packet['ticker']} sentiment event coverage mismatch")
    validated = []
    for event_id, row in sorted(combined.items()):
        item = {
            "event_id": event_id,
            "direction": require_number(row.get("direction"), -1, 1, "direction"),
            "impact": require_number(row.get("impact"), 1, 5, "impact"),
            "relevance": require_number(row.get("relevance"), 0, 1, "relevance"),
            "confidence": require_number(row.get("confidence"), 0, 1, "confidence"),
            "event_type": clean_text(row.get("event_type"), 120),
            "reason": clean_text(row.get("reason"), 600),
            "source_tier": events[event_id].get("source_tier"),
        }
        if not item["event_type"] or not item["reason"]:
            raise LocalReviewError(f"{packet['ticker']} incomplete event classification")
        verification = row.get("verification")
        if verification_required(events[event_id], item):
            if not isinstance(verification, dict) or verification.get("decision") not in VERIFICATION_DECISIONS:
                raise LocalReviewError(f"{packet['ticker']} event requires verification: {event_id}")
            if not clean_text(verification.get("reason"), 600):
                raise LocalReviewError(f"{packet['ticker']} verification reason missing: {event_id}")
            if verification["decision"] == "reject":
                item.update({"relevance": 0.0, "confidence": min(item["confidence"], 0.49)})
            elif verification["decision"] == "downgrade":
                item.update({"impact": min(item["impact"], 3.0), "confidence": min(item["confidence"], 0.69)})
            item["verification"] = dict(verification)
        elif verification is not None:
            item["verification"] = dict(verification)
        validated.append(item)
    return validated


def load_shared_review(input_root: Path, reviews_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    shared = read_json(input_root / "shared.json")
    events = shared["sentiment_raw_evidence"]["event_clusters"]
    path = reviews_dir / "_shared.json"
    if not events and not path.is_file():
        return shared, {"sentiment": {"events": []}}
    payload = read_json(path)
    if (
        payload.get("schema_version") != REVIEW_SCHEMA_VERSION
        or payload.get("execution_mode") != "local_skill"
        or payload.get("skill") != SKILL_NAME
        or payload.get("skill_contract_version") != CONTRACT_VERSION
        or payload.get("input_sha256") != shared.get("input_sha256")
    ):
        raise LocalReviewError("shared industry review provenance mismatch")
    return shared, payload


def aggregate_events(packet: dict[str, Any], reviews: list[dict[str, Any]], tiers: set[str]) -> dict[str, Any]:
    included = [row for row in reviews if row["source_tier"] in tiers and row["relevance"] >= 0.5]
    weight = sum(row["impact"] * row["relevance"] * row["confidence"] for row in included)
    score = None if weight <= 0 else round(50 + 50 * sum(
        row["direction"] * row["impact"] * row["relevance"] * row["confidence"] for row in included
    ) / weight, 2)
    if score is None:
        state = "无正式证据" if tiers == {"A", "B"} else "无上下文证据"
    elif score >= 60:
        state = "偏正面"
    elif score <= 40:
        state = "偏负面"
    else:
        state = "中性"
    return {"status": "unavailable" if score is None else "ok", "score_0_100": score, "state": state,
            "article_count": len(included), "event_reviews": included}


def build_sentiment(manifest: dict[str, Any], packets: dict[str, dict[str, Any]], reviews: dict[str, dict[str, Any]],
                    shared_packet: dict[str, Any], shared_review: dict[str, Any]) -> dict[str, Any]:
    shared_events = validated_event_reviews({**shared_packet, "ticker": "_shared"}, shared_review)
    industry_details: dict[str, dict[str, Any]] = {}
    industries = sorted({
        str(packet["sentiment_raw_evidence"].get("industry") or "") for packet in packets.values()
    } - {""})
    for industry in industries:
        event_ids = {
            row["event_id"] for row in shared_packet["sentiment_raw_evidence"]["event_clusters"]
            if row.get("industry") == industry
        }
        rows = [row for row in shared_events if row["event_id"] in event_ids]
        formal = aggregate_events({"ticker": f"industry:{industry}"}, rows, {"A", "B"})
        context = aggregate_events({"ticker": f"industry:{industry}"}, rows, {"C", "D"})
        industry_details[industry] = {
            "industry": industry,
            "company_count": sum(
                1 for packet in packets.values()
                if packet["sentiment_raw_evidence"].get("industry") == industry
            ),
            "sentiment": {**formal, "formal_sentiment": formal, "context_sentiment": context,
                          "formal_score_0_100": formal["score_0_100"]},
            "local_review": {"event_reviews": rows, "skill_contract_version": CONTRACT_VERSION},
        }
    companies = []
    verification_count = 0
    for ticker, packet in sorted(packets.items()):
        event_reviews = validated_event_reviews(packet, reviews[ticker])
        verification_count += sum(1 for row in event_reviews if row.get("verification"))
        formal = aggregate_events(packet, event_reviews, {"A", "B"})
        context = aggregate_events(packet, event_reviews, {"C", "D"})
        raw = packet["sentiment_raw_evidence"]
        companies.append({
            "company": packet["company"], "ticker": ticker, "market": MARKET,
            "news_sentiment": {**formal, "formal_sentiment": formal, "context_sentiment": context,
                               "formal_score_0_100": formal["score_0_100"], "captured_items": raw["event_clusters"]},
            "combined_sentiment": {**formal, "score_0_100": formal["score_0_100"],
                                   "formal_sentiment": formal, "context_sentiment": context},
            "industry_sentiment": (industry_details.get(str(raw.get("industry") or "")) or {}).get("sentiment"),
            "market_sentiment": raw.get("market_raw"),
            "crowding": raw.get("crowding"),
            "local_review": {"event_reviews": event_reviews, "skill_contract_version": CONTRACT_VERSION},
        })
    return {
        "schema_version": 1, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_cutoff": manifest["date"], "scope": [MARKET], "status": "ok", "llm_status": "local_reviewed",
        "execution_mode": "local_skill", "skill": SKILL_NAME, "skill_contract_version": CONTRACT_VERSION,
        "model_runtime": "local_chatgpt", "provider": None, "model": None, "external_llm_api_requests": 0,
        "company_count": len(companies), "verification_count": verification_count,
        "formal_company_count": sum(
            1 for row in companies if row["news_sentiment"]["formal_score_0_100"] is not None
        ),
        "context_company_count": sum(
            1 for row in companies if row["news_sentiment"]["context_sentiment"]["score_0_100"] is not None
        ),
        "formal_event_count": sum(
            row["news_sentiment"]["formal_sentiment"]["article_count"] for row in companies
        ),
        "context_event_count": sum(
            row["news_sentiment"]["context_sentiment"]["article_count"] for row in companies
        ),
        "industry_count": len(industry_details), "industry_sentiments": industry_details, "companies": companies,
    }


def conservative_state(initial: str, challenge: str) -> str:
    rank = {"证据不足": 0, "暂不构成当前机会": 0, "临近机会": 1, "当前机会": 2}
    return initial if rank[initial] <= rank[challenge] else challenge


def local_result(assessment: dict[str, Any], generated_at: str) -> dict[str, Any]:
    return {"status": "ready", "model": "local_chatgpt", "transport": "local_skill",
            "generated_at": generated_at, "assessment": assessment,
            "reasoning": {"requested": "current Codex/ChatGPT session", "effective": "local_skill",
                          "usage": None}, "schema_repair_attempts": 0}


def build_opportunities(manifest: dict[str, Any], packets: dict[str, dict[str, Any]], reviews: dict[str, dict[str, Any]], *, force: bool = False) -> dict[str, Any]:
    scans = []
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    challenge_count = 0
    reused_count = 0
    for ticker, packet in sorted(packets.items()):
        plan = "reevaluate" if force else packet["review_plan"]["opportunity_action"]
        if plan == "reuse":
            prior = packet.get("previous_review")
            if not isinstance(prior, dict):
                raise LocalReviewError(f"{ticker} missing reusable prior")
            record = dict(prior)
            record.update({"evaluation_mode": "reused_unchanged", "model_request_count": 0,
                           "material_trigger_checked_at": generated_at,
                           "current_projection_context": {"current_input_sha256": packet["input_sha256"]}})
            scans.append(record)
            reused_count += 1
            continue
        opportunity = reviews[ticker].get("opportunity")
        if not isinstance(opportunity, dict):
            raise LocalReviewError(f"{ticker} opportunity review missing")
        initial_assessment = validate_assessment(opportunity.get("initial"), packet, "initial")
        initial_state = initial_assessment["opportunity_state"]
        challenge = opportunity.get("challenge")
        if initial_state in {"当前机会", "临近机会"}:
            if not isinstance(challenge, dict) or challenge.get("decision") not in VERIFICATION_DECISIONS:
                raise LocalReviewError(f"{ticker} candidate requires challenge")
            challenge_assessment = validate_assessment(challenge.get("assessment"), packet, "challenge")
            if initial_state == "临近机会" and challenge_assessment["opportunity_state"] == "当前机会":
                raise LocalReviewError(f"{ticker} challenge cannot promote near to current")
            final_assessment = dict(challenge_assessment)
            final_assessment["opportunity_state"] = conservative_state(initial_state, challenge_assessment["opportunity_state"])
            challenge_count += 1
        else:
            if challenge is not None:
                raise LocalReviewError(f"{ticker} non-candidate must not run challenge")
            challenge_assessment = None
            final_assessment = initial_assessment
        initial = local_result(initial_assessment, generated_at)
        verification = local_result(challenge_assessment, generated_at) if challenge_assessment else None
        final = local_result(final_assessment, generated_at)
        models = {"local_chatgpt": final}
        if final_assessment["opportunity_state"] == "当前机会":
            classification = "当前机会"
        elif final_assessment["opportunity_state"] == "临近机会":
            classification = "临近机会"
        else:
            classification = "暂不进入机会面板" if final_assessment["opportunity_state"] != "证据不足" else "待人工复核"
        scans.append({
            "schema_version": 3, "status": "ready", "company": packet["company"], "ticker": ticker,
            "market": MARKET, "report_path": packet["canonical"]["report"],
            "report_sha256": packet["canonical"]["report_sha256"], "input_sha256": packet["input_sha256"],
            "generated_at": generated_at, "models": models,
            "union": {"included": classification == "当前机会", "near_included": classification == "临近机会",
                      "classification": classification, "supporting_models": ["local_chatgpt"] if classification == "当前机会" else [],
                      "near_models": ["local_chatgpt"] if classification == "临近机会" else [], "model_count": 1,
                      "stale_count": 0, "opportunity_count": int(classification == "当前机会"),
                      "conditional_count": int(classification == "临近机会"),
                      "rule": "本地 Initial + 保守 Challenge；最终买卖由投资者决定。"},
            "initial": initial, "verification": verification, "final": final,
            "verification_required": verification is not None, "input_snapshot": packet,
            "evaluation_mode": "local_skill_evaluated", "model_request_count": 0,
            "local_model_pass_count": 2 if verification else 1,
            "filter_class": "possibly_material", "trigger_reasons": packet["review_plan"]["reasons"],
            "assessment_contract": {"skill": SKILL_NAME, "version": CONTRACT_VERSION},
            "skill_contract_version": CONTRACT_VERSION,
            "material_trigger_fingerprint": packet["materiality"]["fingerprint"],
            "material_trigger_snapshot": packet["materiality"]["snapshot"],
            "material_trigger_checked_at": generated_at, "last_model_evaluated_at": generated_at,
        })
    current = sum(1 for row in scans if row["union"]["classification"] == "当前机会")
    near = sum(1 for row in scans if row["union"]["classification"] == "临近机会")
    insufficient = sum(1 for row in scans if row["union"]["classification"] == "待人工复核")
    not_current = len(scans) - current - near - insufficient
    return {
        "schema_version": 3, "generated_at": generated_at, "completed_at": generated_at, "status": "ok",
        "mode": "local_skill", "market": MARKET,
        "models": [{"role": "initial_and_challenge", "model": "local_chatgpt", "transport": "local_skill"}],
        "execution_mode": "local_skill", "skill": SKILL_NAME, "skill_contract_version": CONTRACT_VERSION,
        "model_runtime": "local_chatgpt", "external_llm_api_requests": 0,
        "scan_count": len(scans), "expected_scan_count": len(scans), "model_result_count": len(scans),
        "model_request_count": 0, "local_model_pass_count": len(scans) - reused_count + challenge_count,
        "reused_count": reused_count, "reevaluated_count": len(scans) - reused_count,
        "verification_request_count": 0, "challenge_count": challenge_count,
        "ready_count": len(scans), "current_opportunity_count": current, "near_opportunity_count": near,
        "not_current_opportunity_count": not_current, "insufficient_evidence_count": insufficient,
        "stale_count": 0, "error_count": 0, "scans": scans,
    }


def authority_hashes(repo_root: Path) -> dict[str, str]:
    result = {}
    for relative in AUTHORITY_PATHS:
        path = repo_root / relative
        if path.is_file():
            result[relative] = file_sha256(path)
        elif path.is_dir():
            result[relative] = value_sha256({
                item.relative_to(path).as_posix(): file_sha256(item)
                for item in sorted(path.rglob("*")) if item.is_file()
            })
    return result


def validate_reviews(input_root: Path, reviews_dir: Path, output_root: Path, repo_root: Path, *, force: bool = False) -> dict[str, Any]:
    manifest, packets = validate_input(input_root)
    shared_packet, shared_review = load_shared_review(input_root, reviews_dir)
    reviews = {}
    for ticker in packets:
        path = reviews_dir / f"{ticker}.json"
        payload = read_json(path)
        if payload.get("schema_version") != REVIEW_SCHEMA_VERSION or payload.get("execution_mode") != "local_skill":
            raise LocalReviewError(f"invalid local review provenance: {ticker}")
        if payload.get("skill") != SKILL_NAME or payload.get("skill_contract_version") != CONTRACT_VERSION:
            raise LocalReviewError(f"local review contract mismatch: {ticker}")
        if payload.get("input_sha256") != packets[ticker]["input_sha256"]:
            raise LocalReviewError(f"local review input binding mismatch: {ticker}")
        reviews[ticker] = payload
    before = authority_hashes(repo_root)
    sentiment = build_sentiment(manifest, packets, reviews, shared_packet, shared_review)
    opportunity = build_opportunities(manifest, packets, reviews, force=force)
    write_json(output_root / "sentiment.json", sentiment)
    write_json(output_root / "opportunity_scans.json", opportunity)
    result = {
        "schema_version": 1, "status": "validated", "date": manifest["date"],
        "execution_mode": "local_skill", "skill": SKILL_NAME, "skill_contract_version": CONTRACT_VERSION,
        "input_manifest_sha256": manifest["manifest_sha256"], "source_sha": manifest["source_sha"],
        "source_data_cutoff": manifest["date"], "authority_sha256": before,
        "review_scope": manifest.get("review_scope"),
        "publication_eligible": manifest.get("publication_eligible") is True,
        "components": {
            "sentiment": {"path": "sentiment.json", "sha256": file_sha256(output_root / "sentiment.json")},
            "opportunity": {"path": "opportunity_scans.json", "sha256": file_sha256(output_root / "opportunity_scans.json")},
        },
        "summary": {"universe": len(packets), "reused": opportunity["reused_count"],
                    "reevaluated": opportunity["reevaluated_count"], "current": opportunity["current_opportunity_count"],
                    "near": opportunity["near_opportunity_count"],
                    "not_current": opportunity["not_current_opportunity_count"],
                    "insufficient": opportunity["insufficient_evidence_count"],
                    "challenge_count": opportunity["challenge_count"],
                    "formal_company_count": sentiment["formal_company_count"],
                    "context_company_count": sentiment["context_company_count"],
                    "formal_event_count": sentiment["formal_event_count"],
                    "context_event_count": sentiment["context_event_count"],
                    "sentiment_verification_count": sentiment["verification_count"],
                    "industry_event_count": manifest["shared"]["industry_event_count"], "authority_changes": 0},
    }
    write_json(output_root / "validation.json", result)
    return result


def apply_validated(repo_root: Path, validated_root: Path) -> dict[str, Any]:
    validation = read_json(validated_root / "validation.json")
    if validation.get("status") != "validated" or validation.get("skill_contract_version") != CONTRACT_VERSION:
        raise LocalReviewError("review transaction is not validated")
    if validation.get("publication_eligible") is not True:
        raise LocalReviewError("partial dry-run transaction cannot be published")
    if authority_hashes(repo_root) != validation.get("authority_sha256"):
        raise LocalReviewError("authority changed after review; refusing apply")
    review_date = date.fromisoformat(str(validation["date"]))
    target = repo_root / PUBLISHED_ROOT / review_date.isoformat()
    target.mkdir(parents=True, exist_ok=True)
    components = {}
    for name, filename in (("sentiment", "sentiment.json"), ("opportunity", "opportunity_scans.json")):
        source = validated_root / filename
        if file_sha256(source) != validation["components"][name]["sha256"]:
            raise LocalReviewError(f"validated component changed: {name}")
        destination = target / filename
        shutil.copy2(source, destination)
        components[name] = {"path": destination.relative_to(repo_root).as_posix(), "sha256": file_sha256(destination)}
    pointer = {
        "schema_version": PUBLISHED_SCHEMA_VERSION, "status": "published_local_review",
        "date": review_date.isoformat(), "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "execution_mode": "local_skill", "skill": SKILL_NAME, "skill_contract_version": CONTRACT_VERSION,
        "source_sha": validation["source_sha"], "source_data_cutoff": validation["source_data_cutoff"],
        "input_manifest_sha256": validation["input_manifest_sha256"], "external_llm_api_requests": 0,
        "components": components,
    }
    write_json(repo_root / PUBLISHED_POINTER, pointer)
    return pointer


def materialize_published(repo_root: Path) -> bool:
    sentiment = load_published_component(repo_root, "sentiment")
    opportunity = load_published_component(repo_root, "opportunity")
    if sentiment is None and opportunity is None:
        return False
    if sentiment is None or opportunity is None:
        raise LocalReviewError("published local review transaction is incomplete")
    write_json(repo_root / "data/sentiment/latest.json", sentiment)
    write_json(repo_root / "site/data/sentiment.json", sentiment)
    write_json(repo_root / "data/investment-dashboard/opportunity_scans.json", opportunity)
    return True


def sync_input(repo_root: Path, runtime_root: Path, *, remote: str = "origin", branch: str = "vps-generated") -> dict[str, Any]:
    """Fetch one proven input transaction without merging the generated branch."""
    fetched = subprocess.run(
        ["git", "fetch", remote, f"{branch}:refs/remotes/{remote}/{branch}"],
        cwd=repo_root, check=False, capture_output=True, text=True,
    )
    if fetched.returncode:
        raise LocalReviewError(f"cannot fetch {remote}/{branch}: {fetched.stderr.strip()}")
    ref = f"refs/remotes/{remote}/{branch}"
    pointer_path = "data/local-daily-review/input/latest.json"
    shown = subprocess.run(["git", "show", f"{ref}:{pointer_path}"], cwd=repo_root,
                           check=False, capture_output=True)
    if shown.returncode:
        raise LocalReviewError(f"generated branch has no ready marker: {remote}/{branch}")
    try:
        pointer = json.loads(shown.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LocalReviewError("generated input pointer is invalid") from exc
    if pointer.get("status") != "awaiting_local_review" or pointer.get("market") != MARKET:
        raise LocalReviewError("generated input is not ready for A-share local review")
    source_path = str(pointer.get("path") or "").strip("/")
    expected_prefix = f"data/local-daily-review/input/{pointer.get('date')}"
    if source_path != expected_prefix:
        raise LocalReviewError("generated input path/date mismatch")
    archived = subprocess.run(["git", "archive", "--format=tar", ref, source_path], cwd=repo_root,
                              check=False, capture_output=True)
    if archived.returncode:
        raise LocalReviewError("cannot read generated input transaction")
    destination = runtime_root / str(pointer["date"]) / "input"
    if destination.is_dir():
        current = read_json(destination / "manifest.json")
        if current.get("manifest_sha256") == pointer.get("manifest_sha256"):
            manifest, _ = validate_input(destination)
            return {"status": "already_synced", "date": manifest["date"], "input_root": str(destination)}
        raise LocalReviewError(f"different local input already exists: {destination}")
    runtime_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".input-", dir=runtime_root))
    try:
        extracted = temporary / "input"
        extracted.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(archived.stdout), mode="r:") as bundle:
            for member in bundle.getmembers():
                if not member.isfile():
                    continue
                name = Path(member.name)
                try:
                    relative = name.relative_to(source_path)
                except ValueError as exc:
                    raise LocalReviewError("generated archive escaped input root") from exc
                target = (extracted / relative).resolve()
                if not target.is_relative_to(extracted.resolve()):
                    raise LocalReviewError("generated archive contains unsafe path")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                if source is None:
                    raise LocalReviewError("generated archive member is unreadable")
                target.write_bytes(source.read())
        manifest, _ = validate_input(extracted)
        if manifest.get("manifest_sha256") != pointer.get("manifest_sha256"):
            raise LocalReviewError("generated pointer/manifest hash mismatch")
        destination.parent.mkdir(parents=True, exist_ok=True)
        extracted.replace(destination)
        return {"status": "synced", "date": manifest["date"], "input_root": str(destination),
                "source_sha": manifest["source_sha"]}
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def command_prepare(args: argparse.Namespace) -> int:
    payload = prepare(args.repo_root.resolve(), args.output_root.resolve(), args.date, args.raw_sentiment.resolve(),
                      force=args.force, tickers=set(args.ticker) if args.ticker else None)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def command_status(args: argparse.Namespace) -> int:
    manifest, packets = validate_input(args.input_root.resolve())
    print(json.dumps({"status": "ready", "date": manifest["date"], "company_count": len(packets),
                      "reevaluate_count": manifest["reevaluate_count"], "reuse_count": manifest["reuse_count"]},
                     ensure_ascii=False, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    payload = validate_reviews(args.input_root.resolve(), args.reviews_dir.resolve(), args.output_root.resolve(), args.repo_root.resolve(), force=args.force)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def command_apply(args: argparse.Namespace) -> int:
    print(json.dumps(apply_validated(args.repo_root.resolve(), args.validated_root.resolve()), ensure_ascii=False, sort_keys=True))
    return 0


def command_materialize(args: argparse.Namespace) -> int:
    print(json.dumps({"materialized": materialize_published(args.repo_root.resolve())}, sort_keys=True))
    return 0


def command_sync_input(args: argparse.Namespace) -> int:
    payload = sync_input(args.repo_root.resolve(), args.runtime_root.resolve(), remote=args.remote, branch=args.branch)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    prepare_cmd = sub.add_parser("prepare")
    prepare_cmd.add_argument("--repo-root", type=Path, default=ROOT)
    prepare_cmd.add_argument("--output-root", type=Path, required=True)
    prepare_cmd.add_argument("--raw-sentiment", type=Path, required=True)
    prepare_cmd.add_argument("--date", type=date.fromisoformat, required=True)
    prepare_cmd.add_argument("--force", action="store_true")
    prepare_cmd.add_argument("--ticker", action="append", help="A-share ticker for non-publishable partial dry-run")
    prepare_cmd.set_defaults(handler=command_prepare)
    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--input-root", type=Path, required=True)
    status_cmd.set_defaults(handler=command_status)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--repo-root", type=Path, default=ROOT)
    validate_cmd.add_argument("--input-root", type=Path, required=True)
    validate_cmd.add_argument("--reviews-dir", type=Path, required=True)
    validate_cmd.add_argument("--output-root", type=Path, required=True)
    validate_cmd.add_argument("--force", action="store_true")
    validate_cmd.set_defaults(handler=command_validate)
    apply_cmd = sub.add_parser("apply")
    apply_cmd.add_argument("--repo-root", type=Path, default=ROOT)
    apply_cmd.add_argument("--validated-root", type=Path, required=True)
    apply_cmd.set_defaults(handler=command_apply)
    materialize_cmd = sub.add_parser("materialize")
    materialize_cmd.add_argument("--repo-root", type=Path, default=ROOT)
    materialize_cmd.set_defaults(handler=command_materialize)
    sync_cmd = sub.add_parser("sync-input")
    sync_cmd.add_argument("--repo-root", type=Path, default=ROOT)
    sync_cmd.add_argument("--runtime-root", type=Path, default=ROOT / ".runtime/local-review")
    sync_cmd.add_argument("--remote", default="origin")
    sync_cmd.add_argument("--branch", default="vps-generated")
    sync_cmd.set_defaults(handler=command_sync_input)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except LocalReviewError as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
