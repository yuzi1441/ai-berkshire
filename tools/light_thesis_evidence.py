#!/usr/bin/env python3
"""Prepare an auditable fresh-evidence package for a WATCH light thesis check.

The tool is deliberately model-free and authority-free.  It reuses existing
local review, CNINFO, news, Event Radar, and rule-evaluation capabilities,
filters them against the current main-report baseline, and emits one transient
package for the current Codex client session to review with Luna.  It never
writes light thesis signals or any decision state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import main_report_review
import sentiment_snapshot


SCHEMA_VERSION = 1
SHANGHAI = ZoneInfo("Asia/Shanghai")
STATE_PATH = Path("data/investment-dashboard/company_state.json")
RULE_PACKAGE_DIRECTORY = Path("data/investment-dashboard/main-report-review-rules")
EVENT_RADAR_PATH = Path("data/investment-dashboard/event_radar.json")
QUOTES_PATH = Path("data/investment-dashboard/quotes/latest.json")
CURRENT_SOURCE_ROLES = {
    "local_current_evidence",
    "official_current_evidence",
    "zcode_current_evidence_extract",
}
EVIDENCE_TYPES = {
    "financial_report",
    "earnings_preannouncement",
    "company_announcement",
    "important_news",
    "structured_event",
    "rule_evaluation",
    "local_document",
}

_DATE = re.compile(
    r"(?P<year>20\d{2})\s*(?:年|[-/.])\s*(?P<month>\d{1,2})"
    r"\s*(?:月|[-/.])\s*(?P<day>\d{1,2})\s*日?"
)
_CUTOFF_LABEL = re.compile(
    r"(?:^|[>\s|*_：:])"
    r"(?P<label>(?:研究资料|资料|信息|数据)(?:截至|截止(?:日|日期)?))\s*[：:]?"
)
_REPORT_DATE_LABEL = re.compile(
    r"(?P<label>报告日期|研究日期|研究基准日|报告完成日|撰写日期|建立日期|更新日期|工作日期|日期)"
    r"\s*[：:]?"
)
_FINANCIAL_TOKENS = re.compile(r"年度报告|年报|半年度报告|半年报|季度报告|季报|财务报告")
_PREANNOUNCEMENT_TOKENS = re.compile(r"业绩预告|业绩快报|盈利预告|盈警")
_ANNOUNCEMENT_TOKENS = re.compile(
    r"合同|订单|中标|资本开支|回购|减持|管理层|董事长|董事任命|董事辞职|独立董事任职资格|"
    r"监事任命|监事辞职|总经理|高管|任命|辞职|换届|"
    r"诉讼|处罚|监管|事故|停产|收购|出售|重组|破产|违约|担保|分红|股权激励|"
    r"项目|产能|产品召回|关税|政策|控制权|客户流失|竞争|市场份额|价格战|供应链"
)
_NOISE_TOKENS = re.compile(
    r"股价|涨停|跌停|行情|资金流(?:入|出|向)|龙虎榜|技术面|均线|目标价|"
    r"融资融券|十大流通股东|券商身影|机构持仓|主力资金"
)
_ALWAYS_NOISE_TOKENS = re.compile(
    r"资金流(?:入|出|向)|龙虎榜|融资融券|十大流通股东|券商身影|机构持仓|主力资金"
)
_GENERIC_NOTICE_TOKENS = re.compile(
    r"临时股东会|股东大会|法律意见书|投资者集体接待日|"
    r"关于.*召开.*业绩说明会|业绩说明会.*(?:通知|公告)|"
    r"续聘会计师事务所|闲置资金|现金管理|董事会第.{0,24}次会议决议|董事会会议决议|核查意见|"
    r"管理制度|议事规则|工作规则|工作制度|管理办法|多元化政策|公司章程"
)
_HARD_MATERIAL_TOKENS = re.compile(
    rf"{_FINANCIAL_TOKENS.pattern}|{_PREANNOUNCEMENT_TOKENS.pattern}|"
    r"合同|订单|中标|资本开支|回购|减持|董事长|总经理|高管|任命|辞职|控制权|"
    r"诉讼|处罚|监管|事故|停产|收购|出售|重组|破产|违约|担保|产品召回|客户流失"
)


class EvidenceError(ValueError):
    """Raised when an evidence package cannot be prepared safely."""


def _text(value: Any, limit: int | None = None) -> str:
    result = " ".join(str(value or "").split())
    return result[:limit] if limit is not None else result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"invalid or missing JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"expected JSON object: {path}")
    return value


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_dates(value: str) -> list[str]:
    parsed: list[str] = []
    for match in _DATE.finditer(value):
        try:
            parsed.append(
                date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                ).isoformat()
            )
        except ValueError:
            continue
    return parsed


def resolve_baseline_cutoff(report_path: Path) -> dict[str, Any]:
    """Resolve a labelled report/evidence cutoff and fail closed if absent.

    A generic data/资料/信息 cutoff is more precise than a report date.  A
    category-only period such as ``财务数据截止：2026-03-31`` is intentionally
    not treated as the whole-report cutoff; the labelled report/research date
    remains the safe boundary for evidence published after the report.
    """
    if not report_path.is_file():
        raise EvidenceError(f"missing baseline report: {report_path}")
    lines = report_path.read_text(encoding="utf-8", errors="replace").splitlines()[:100]
    candidates: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        cutoff = _CUTOFF_LABEL.search(line)
        if cutoff:
            dates = _parse_dates(line[cutoff.end() :])
            if dates:
                candidates.append(
                    {
                        "cutoff": max(dates),
                        "source_kind": "explicit_evidence_cutoff",
                        "source_label": cutoff.group("label"),
                        "source_line": line_number,
                        "source_text": _text(line, 500),
                        "priority": 0,
                    }
                )
        report_date = _REPORT_DATE_LABEL.search(line)
        if report_date:
            dates = _parse_dates(line[report_date.end() :])
            if dates:
                candidates.append(
                    {
                        "cutoff": dates[0],
                        "source_kind": "explicit_report_date",
                        "source_label": report_date.group("label"),
                        "source_line": line_number,
                        "source_text": _text(line, 500),
                        "priority": 1,
                    }
                )
    if not candidates:
        raise EvidenceError(
            f"baseline report has no labelled evidence/report date: {report_path}"
        )
    selected = min(candidates, key=lambda row: (row["priority"], -int(row["cutoff"].replace("-", "")), row["source_line"]))
    return {key: value for key, value in selected.items() if key != "priority"}


def _document_type(document: dict[str, Any]) -> str:
    text = " ".join(
        _text(document.get(key))
        for key in ("title", "path", "fact_summary", "content")
    )
    if _PREANNOUNCEMENT_TOKENS.search(text):
        return "earnings_preannouncement"
    if "业绩说明会" in text:
        return "company_announcement"
    if _FINANCIAL_TOKENS.search(text):
        return "financial_report"
    if document.get("source_role") == "official_current_evidence" or _ANNOUNCEMENT_TOKENS.search(text):
        return "company_announcement"
    return "local_document"


def _content_hash(document: dict[str, Any], fact: str) -> str:
    candidate = _text(document.get("canonical_sha256")).lower()
    source_document_sha256 = candidate if re.fullmatch(r"[0-9a-f]{64}", candidate) else None
    # The model consumes the selected concise fact, not the entire source
    # document.  Hash both so a changed source or changed deterministic
    # extraction necessarily changes the light-thesis input fingerprint.
    return canonical_json_sha256(
        {
            "source_document_sha256": source_document_sha256,
            "concise_fact": fact,
        }
    )


def document_to_evidence(document: dict[str, Any]) -> dict[str, Any] | None:
    if document.get("source_role") not in CURRENT_SOURCE_ROLES:
        return None
    source_identity = _text(document.get("path"))
    document_date = _text(document.get("document_date"))[:10]
    content = _text(document.get("content"), 1600)
    fact = _text(document.get("fact_summary"), 1600) or _text(document.get("title"), 500)
    if content and content not in fact:
        fact = _text(f"{fact} {content}", 1600)
    if not source_identity or not document_date or not fact:
        return None
    if _GENERIC_NOTICE_TOKENS.search(_text(document.get("title"))):
        return None
    content_sha256 = _content_hash(document, fact)
    identity = canonical_json_sha256(
        {
            "source_identity": source_identity,
            "document_date": document_date,
            "content_sha256": content_sha256,
        }
    )
    provenance = {
        key: document.get(key)
        for key in (
            "source_role",
            "path",
            "canonical_sha256",
            "selected_pages",
            "page_count",
            "selection_method",
            "provenance",
        )
        if document.get(key) not in (None, "", [])
    }
    return {
        "evidence_id": f"document:{identity[:20]}",
        "type": _document_type(document),
        "date": document_date,
        "source": _text(document.get("title")) or source_identity,
        "source_identity": source_identity,
        "concise_fact": fact,
        "provenance": provenance,
        "content_sha256": content_sha256,
    }


def news_to_evidence(article: dict[str, Any]) -> dict[str, Any] | None:
    published_at = _text(article.get("published_at"))
    title = _text(article.get("title"), 500)
    summary = _text(article.get("summary"), 1200)
    combined = f"{title} {summary}".strip()
    tier = _text(article.get("source_tier")).upper()
    if not published_at or not title or tier not in {"A", "B"}:
        return None
    score = sentiment_snapshot.lexical_score(article)
    company_terms = {
        re.sub(r"\s+", "", _text(article.get("display_name"))).casefold(),
        re.sub(r"\s+", "", _text(article.get("company"))).casefold(),
        re.sub(r"\D", "", _text(article.get("ticker"))),
    }
    lowered = re.sub(r"\s+", "", combined).casefold()
    if article.get("source_via") != "cninfo_direct" and not any(
        term and term in lowered for term in company_terms
    ):
        return None
    material = bool(
        _FINANCIAL_TOKENS.search(combined)
        or _PREANNOUNCEMENT_TOKENS.search(combined)
        or _ANNOUNCEMENT_TOKENS.search(combined)
    )
    if not material or score.get("relevance", 0) < 0.6:
        return None
    if _ALWAYS_NOISE_TOKENS.search(combined) or _GENERIC_NOTICE_TOKENS.search(title):
        return None
    if _NOISE_TOKENS.search(combined) and not _HARD_MATERIAL_TOKENS.search(combined):
        return None
    identity = sentiment_snapshot.news_identity_key(article)
    content_sha256 = canonical_json_sha256(
        {
            "identity": identity,
            "title": title,
            "summary": summary,
            "published_at": published_at,
            "publisher": _text(article.get("publisher")),
        }
    )
    return {
        "evidence_id": f"news:{sentiment_snapshot.stable_news_id(identity)}",
        "type": "company_announcement" if article.get("source_via") == "cninfo_direct" else "important_news",
        "date": published_at[:10],
        "source": _text(article.get("publisher")) or _text(article.get("source")) or "company news",
        "source_identity": sentiment_snapshot.canonical_news_url(article.get("url")) or identity,
        "concise_fact": combined[:1600],
        "provenance": {
            key: article.get(key)
            for key in (
                "url",
                "publisher",
                "source_via",
                "source_tier",
                "verification_status",
                "published_at",
                "company",
                "ticker",
            )
            if article.get(key) not in (None, "")
        },
        "content_sha256": content_sha256,
        "structured_value": {
            "event_type": score.get("event_type"),
            "impact": score.get("impact"),
            "relevance": score.get("relevance"),
            "filter": "deterministic_lexicon_and_material_terms",
        },
    }


def evidence_item_is_relevant(item: dict[str, Any]) -> bool:
    """Apply the same fail-closed noise guard to transformed evidence items."""
    item_type = item.get("type")
    provenance = item.get("provenance") or {}
    text = _text(item.get("concise_fact"))
    heading = re.split(r"\s+\[PDF|\s+巨潮资讯官方公告", text, maxsplit=1)[0]
    if item_type in EVIDENCE_TYPES and _GENERIC_NOTICE_TOKENS.search(heading):
        return False
    if item_type == "rule_evaluation":
        source = _text(provenance.get("evidence_source") or item.get("source")).casefold()
        identity = _text(item.get("source_identity")).casefold()
        if "quote" in source or "行情" in source or "price" in identity:
            return False
    if item_type == "important_news" or (
        item_type == "company_announcement"
        and provenance.get("source_via")
        and provenance.get("source_role") != "official_current_evidence"
    ):
        material = bool(
            _FINANCIAL_TOKENS.search(text)
            or _PREANNOUNCEMENT_TOKENS.search(text)
            or _ANNOUNCEMENT_TOKENS.search(text)
        )
        if not material:
            return False
        if _ALWAYS_NOISE_TOKENS.search(text) or _GENERIC_NOTICE_TOKENS.search(text):
            return False
        if _NOISE_TOKENS.search(text) and not _HARD_MATERIAL_TOKENS.search(text):
            return False
    return True


def collect_structured_evidence(
    repo_root: Path,
    company: dict[str, Any],
) -> list[dict[str, Any]]:
    """Reuse only current structured facts that already carry provenance."""
    ticker = _text(company.get("ticker")).upper()
    items: list[dict[str, Any]] = []
    for rule in (company.get("decision_rules") or {}).get("rules") or []:
        if not isinstance(rule, dict):
            continue
        rule_type = _text(rule.get("type")).upper()
        if rule_type.startswith("PRICE"):
            continue
        evaluation = rule.get("evaluation") or {}
        result = _text(evaluation.get("result") or rule.get("status"))
        evidence_date = _text(evaluation.get("evidence_date"))[:10]
        evidence_source = _text(evaluation.get("evidence_source"))
        if result not in {"triggered", "not_triggered", "met", "not_met"}:
            continue
        if not evidence_date or not evidence_source:
            continue
        fact = _text(
            f"{rule.get('condition')}: {result}; {evaluation.get('reason') or ''}",
            1600,
        )
        identity = f"company_state.json#{ticker}/{rule.get('rule_id')}"
        content_sha256 = canonical_json_sha256(
            {
                "rule_id": rule.get("rule_id"),
                "result": result,
                "actual_value": evaluation.get("actual_value"),
                "period": evaluation.get("period"),
                "evidence_source": evidence_source,
                "evidence_date": evidence_date,
                "reason": evaluation.get("reason"),
            }
        )
        items.append(
            {
                "evidence_id": f"rule:{content_sha256[:20]}",
                "type": "rule_evaluation",
                "date": evidence_date,
                "source": evidence_source,
                "source_identity": identity,
                "concise_fact": fact,
                "provenance": {
                    "path": str(STATE_PATH),
                    "rule_id": rule.get("rule_id"),
                    "evidence_source": evidence_source,
                    "evidence_date": evidence_date,
                },
                "content_sha256": content_sha256,
                "structured_value": {
                    "result": result,
                    "actual_value": evaluation.get("actual_value"),
                    "period": evaluation.get("period"),
                },
            }
        )

    radar_path = repo_root / EVENT_RADAR_PATH
    if radar_path.is_file():
        radar = _read_json(radar_path)
        radar_company = next(
            (
                row
                for row in radar.get("companies") or []
                if isinstance(row, dict) and _text(row.get("ticker")).upper() == ticker
            ),
            None,
        )
        for event in (radar_company or {}).get("events") or []:
            if not isinstance(event, dict) or not (
                event.get("thesis_relevant") is True
                or event.get("state") in {"important", "critical"}
            ):
                continue
            published_at = _text(event.get("published_at"))
            if not published_at:
                continue
            fact = _text(event.get("summary") or event.get("headline"), 1600)
            evidence = [row for row in event.get("evidence") or [] if isinstance(row, dict)]
            content_sha256 = canonical_json_sha256(
                {
                    "event_id": event.get("event_id"),
                    "state": event.get("state"),
                    "fact": fact,
                    "evidence": evidence,
                }
            )
            items.append(
                {
                    "evidence_id": f"event:{content_sha256[:20]}",
                    "type": "structured_event",
                    "date": published_at[:10],
                    "source": "Event Radar",
                    "source_identity": f"event_radar.json#{event.get('event_id')}",
                    "concise_fact": fact,
                    "provenance": {
                        "path": str(EVENT_RADAR_PATH),
                        "event_id": event.get("event_id"),
                        "evidence": evidence,
                    },
                    "content_sha256": content_sha256,
                    "structured_value": {
                        "state": event.get("state"),
                        "event_type": event.get("event_type"),
                        "thesis_relevant": event.get("thesis_relevant"),
                    },
                }
            )
    return items


def filter_and_dedupe_evidence(
    items: Iterable[dict[str, Any]],
    *,
    baseline_cutoff: str,
) -> list[dict[str, Any]]:
    """Keep strictly post-baseline facts and deduplicate deterministically."""
    materialized = [item for item in items if isinstance(item, dict)]
    official_identities = {
        _text(item.get("source_identity"))
        for item in materialized
        if (item.get("provenance") or {}).get("source_role")
        in {"official_current_evidence", "local_current_evidence"}
    }
    official_financial_dates = {
        _text(item.get("date"))[:10]
        for item in materialized
        if item.get("type") == "financial_report"
        and (item.get("provenance") or {}).get("source_role") == "official_current_evidence"
    }
    selected: dict[str, dict[str, Any]] = {}
    content_seen: set[str] = set()
    for item in materialized:
        if item.get("type") not in EVIDENCE_TYPES:
            continue
        if not evidence_item_is_relevant(item):
            continue
        provenance = item.get("provenance") or {}
        if (
            provenance.get("source_via") == "cninfo_direct"
            and _text(item.get("source_identity")) in official_identities
        ):
            continue
        evidence_date = _text(item.get("date"))[:10]
        if not evidence_date or evidence_date <= baseline_cutoff:
            continue
        if (
            item.get("type") == "important_news"
            and _FINANCIAL_TOKENS.search(_text(item.get("concise_fact")))
            and evidence_date in official_financial_dates
        ):
            continue
        content_hash = _text(item.get("content_sha256")).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
            continue
        identity = _text(item.get("source_identity"))
        if not identity or not _text(item.get("concise_fact")):
            continue
        dedupe_key = content_hash
        if dedupe_key in content_seen:
            continue
        content_seen.add(dedupe_key)
        stable_key = canonical_json_sha256(
            {
                "type": item.get("type"),
                "date": evidence_date,
                "source_identity": identity,
                "content_sha256": content_hash,
            }
        )
        normalized = dict(item)
        normalized["date"] = evidence_date
        selected[stable_key] = normalized
    return [
        selected[key]
        for key in sorted(
            selected,
            key=lambda key: (
                selected[key]["date"],
                selected[key]["type"],
                selected[key]["source_identity"],
                key,
            ),
        )
    ]


def evidence_fingerprint(
    *,
    baseline_report_sha256: str,
    baseline_cutoff: str,
    evidence_items: list[dict[str, Any]],
) -> str:
    """Hash only the baseline and the exact canonical evidence set."""
    return canonical_json_sha256(
        {
            "baseline_report_sha256": baseline_report_sha256,
            "baseline_cutoff": baseline_cutoff,
            "evidence": [
                {
                    "type": item.get("type"),
                    "date": item.get("date"),
                    "source_identity": item.get("source_identity"),
                    "content_sha256": item.get("content_sha256"),
                }
                for item in evidence_items
            ],
        }
    )


def assemble_package(
    *,
    company: dict[str, Any],
    baseline: dict[str, Any],
    evidence_items: Iterable[dict[str, Any]],
    prepared_at: str,
    acquisition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_hash = _text(company.get("canonical_report_sha256")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", report_hash):
        raise EvidenceError("invalid canonical baseline report SHA")
    cutoff = _text(baseline.get("cutoff"))
    filtered = filter_and_dedupe_evidence(evidence_items, baseline_cutoff=cutoff)
    fingerprint = evidence_fingerprint(
        baseline_report_sha256=report_hash,
        baseline_cutoff=cutoff,
        evidence_items=filtered,
    )
    package = {
        "schema_version": SCHEMA_VERSION,
        "purpose": "fresh_evidence_light_thesis_input",
        "ticker": _text(company.get("ticker")).upper(),
        "company": _text(company.get("company")),
        "market": company.get("market"),
        "lifecycle": company.get("lifecycle"),
        "baseline_report_path": company.get("canonical_report"),
        "baseline_report_sha256": report_hash,
        "baseline_cutoff": cutoff,
        "baseline_cutoff_provenance": {
            key: baseline.get(key)
            for key in ("source_kind", "source_label", "source_line", "source_text")
        },
        "input_status": "ready" if filtered else "no_fresh_evidence",
        "evidence_items": filtered,
        "latest_evidence_at": max((item["date"] for item in filtered), default=None),
        "evidence_fingerprint": fingerprint,
        "prepared_at": prepared_at,
        "acquisition": acquisition or {},
        "review_contract": {
            "allowed_signals": [
                "improved",
                "unchanged",
                "weakened",
                "insufficient_evidence",
            ],
            "forbidden_outputs": [
                "formal_drift_decision",
                "buy_or_sell",
                "position_sizing",
                "lifecycle_change",
                "next_action_change",
                "checklist_eligibility",
            ],
        },
    }
    validate_package(package)
    return package


def validate_package(package: dict[str, Any]) -> None:
    errors: list[str] = []
    if package.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid schema_version")
    if package.get("purpose") != "fresh_evidence_light_thesis_input":
        errors.append("invalid purpose")
    if package.get("market") != "A股" or package.get("lifecycle") != "WATCH":
        errors.append("package must be A股 WATCH")
    report_hash = _text(package.get("baseline_report_sha256")).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", report_hash):
        errors.append("invalid baseline_report_sha256")
    cutoff = _text(package.get("baseline_cutoff"))
    try:
        date.fromisoformat(cutoff)
    except ValueError:
        errors.append("invalid baseline_cutoff")
    items = package.get("evidence_items")
    if not isinstance(items, list):
        errors.append("evidence_items must be a list")
        items = []
    else:
        canonical = filter_and_dedupe_evidence(items, baseline_cutoff=cutoff)
        if canonical != items:
            errors.append("evidence_items are not canonical, fresh, and unique")
    expected_status = "ready" if items else "no_fresh_evidence"
    if package.get("input_status") != expected_status:
        errors.append("input_status does not match evidence_items")
    expected_latest = max((item.get("date") for item in items), default=None)
    if package.get("latest_evidence_at") != expected_latest:
        errors.append("latest_evidence_at does not match evidence_items")
    expected_fingerprint = evidence_fingerprint(
        baseline_report_sha256=report_hash,
        baseline_cutoff=cutoff,
        evidence_items=items,
    )
    if package.get("evidence_fingerprint") != expected_fingerprint:
        errors.append("evidence_fingerprint does not match package input")
    if errors:
        raise EvidenceError("invalid light thesis evidence package: " + "; ".join(errors))


def _current_company(repo_root: Path, ticker: str) -> dict[str, Any]:
    state = _read_json(repo_root / STATE_PATH)
    matches = [
        row
        for row in state.get("companies") or []
        if isinstance(row, dict) and _text(row.get("ticker")).upper() == ticker
    ]
    if len(matches) != 1:
        raise EvidenceError(f"ticker must resolve to one company: {ticker}")
    company = matches[0]
    if company.get("market") != "A股" or company.get("lifecycle") != "WATCH":
        raise EvidenceError(f"fresh light thesis only accepts A股 WATCH: {ticker}")
    return company


def _rule_package(repo_root: Path, company: dict[str, Any]) -> dict[str, Any]:
    ticker = _text(company.get("ticker")).upper()
    package = _read_json(repo_root / RULE_PACKAGE_DIRECTORY / f"{ticker}.json")
    main_report_review.validate_rule_package(package)
    main_report = package.get("main_report") or {}
    if (
        main_report.get("path") != company.get("canonical_report")
        or main_report.get("canonical_sha256") != company.get("canonical_report_sha256")
    ):
        raise EvidenceError(f"review package baseline is not current: {ticker}")
    return package


def _display_name(repo_root: Path, company: dict[str, Any]) -> str:
    """Prefer the exchange quote name when report-library names are aliases."""
    ticker = _text(company.get("ticker")).upper()
    quotes_path = repo_root / QUOTES_PATH
    if quotes_path.is_file():
        quotes = _read_json(quotes_path)
        match = next(
            (
                row
                for row in quotes.get("quotes") or []
                if isinstance(row, dict) and _text(row.get("ticker")).upper() == ticker
            ),
            None,
        )
        name = _text((match or {}).get("name"))
        if name:
            return name
    return _text(company.get("company"))


def prepare_for_ticker(
    repo_root: Path,
    ticker: str,
    *,
    as_of: datetime | None = None,
    include_official: bool = True,
    include_news: bool = True,
    local_collector: Callable[..., list[dict[str, Any]]] | None = None,
    official_collector: Callable[..., list[dict[str, Any]]] | None = None,
    news_collector: Callable[..., tuple[list[dict[str, Any]], list[str]]] | None = None,
) -> dict[str, Any]:
    """Prepare one package without invoking a model or writing authority."""
    repo_root = repo_root.resolve()
    ticker = _text(ticker).upper()
    company = _current_company(repo_root, ticker)
    package = _rule_package(repo_root, company)
    display_name = _display_name(repo_root, company)
    report_path = repo_root / str(company.get("canonical_report"))
    baseline = resolve_baseline_cutoff(report_path)
    cutoff = baseline["cutoff"]
    as_of = as_of or datetime.now(SHANGHAI)
    local_collector = local_collector or main_report_review.collect_local_evidence
    official_collector = official_collector or main_report_review.collect_official_evidence
    news_collector = news_collector or sentiment_snapshot.fetch_company_news_result

    raw_items: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    errors: list[str] = []

    local_documents = local_collector(repo_root, package, baseline_date=cutoff)
    local_items = [item for item in (document_to_evidence(row) for row in local_documents) if item]
    raw_items.extend(local_items)
    source_counts["local_current"] = len(local_items)

    if include_official:
        lookback_days = max(1, (as_of.date() - date.fromisoformat(cutoff)).days + 1)
        official_documents = official_collector(
            package,
            lookback_days=lookback_days,
            baseline_date=cutoff,
        )
        official_items = [item for item in (document_to_evidence(row) for row in official_documents) if item]
        raw_items.extend(official_items)
        source_counts["official"] = len(official_items)

    if include_news:
        lookback_days = max(1, (as_of.date() - date.fromisoformat(cutoff)).days + 1)
        articles, news_errors = news_collector(
            {
                "company": _text(company.get("company")),
                "ticker": ticker,
                "market": "A股",
            },
            display_name=display_name,
            cutoff=as_of,
            lookback_days=lookback_days,
            news_limit=40,
            auxiliary_news_limit=40,
            context_analysis_limit=0,
            fallback_lookback_days=lookback_days,
        )
        news_items = [item for item in (news_to_evidence(row) for row in articles) if item]
        raw_items.extend(news_items)
        source_counts["important_news"] = len(news_items)
        errors.extend(_text(error) for error in news_errors if _text(error))

    structured = collect_structured_evidence(repo_root, company)
    raw_items.extend(structured)
    source_counts["existing_structured"] = len(structured)
    return assemble_package(
        company=company,
        baseline=baseline,
        evidence_items=raw_items,
        prepared_at=as_of.isoformat(timespec="seconds"),
        acquisition={
            "mode": "existing_collectors_plus_deterministic_filter",
            "source_counts_before_cutoff_and_dedup": source_counts,
            "source_errors": sorted(set(errors)),
            "official_enabled": include_official,
            "news_enabled": include_news,
        },
    )


def audit_baselines(repo_root: Path) -> dict[str, Any]:
    state = _read_json(repo_root / STATE_PATH)
    rows = [
        row
        for row in state.get("companies") or []
        if isinstance(row, dict)
        and row.get("market") == "A股"
        and row.get("lifecycle") == "WATCH"
    ]
    results = []
    errors = []
    for company in rows:
        ticker = _text(company.get("ticker")).upper()
        try:
            _rule_package(repo_root, company)
            baseline = resolve_baseline_cutoff(
                repo_root / str(company.get("canonical_report"))
            )
            results.append({"ticker": ticker, **baseline})
        except (EvidenceError, ValueError) as exc:
            errors.append({"ticker": ticker, "error": str(exc)})
    return {
        "eligible_count": len(rows),
        "resolved_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("audit-baselines")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--input", type=Path, required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--ticker", required=True)
    prepare.add_argument("--output", type=Path)
    prepare.add_argument("--local-only", action="store_true")
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    if arguments.command == "audit-baselines":
        payload = audit_baselines(repo_root)
    elif arguments.command == "validate":
        payload = _read_json(arguments.input)
        validate_package(payload)
        print("light thesis evidence package valid")
        return 0
    else:
        payload = prepare_for_ticker(
            repo_root,
            arguments.ticker,
            include_official=not arguments.local_only,
            include_news=not arguments.local_only,
        )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    output = getattr(arguments, "output", None)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if payload.get("error_count") else 0


if __name__ == "__main__":
    raise SystemExit(main())
