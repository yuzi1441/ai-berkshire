#!/usr/bin/env python3
"""Incrementally synchronize Decision Rules after a canonical report change.

This is deliberately a migration/synchronization command, not a dashboard
builder.  A normal build keeps loading the persisted Rule projection.  When a
canonical report is materially changed, this module compares only the Rules
whose source section changed and records KEEP / UPDATE / ADD / RETIRE without
creating a second active copy of an updated Rule.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import decision_rule_extractor  # noqa: E402
import decision_state  # noqa: E402
from source_hash import canonical_file_sha256, markdown_sections, source_metadata_for_excerpt  # noqa: E402


RULE_ACTIONS = ("KEEP", "UPDATE", "ADD", "RETIRE")
LIFECYCLE_RELATIVE = Path("data/investment-dashboard/rule_lifecycle.json")
CHANGE_LOG_RELATIVE = Path("data/investment-dashboard/rule_change_log.json")
_PUNCT_RE = re.compile(r"[\s，,；;。！？!?：:（）()\[\]{}\"'`]+")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_PRICE_WORD_RE = re.compile(r"股价|价格|价位|元|港元|港币|美元|HK\$|USD|CNY|RMB|PE|PB|PS", re.I)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load(path: Path, default: Any) -> Any:
    return decision_state.load_json(path, default)


def _write(path: Path, payload: dict[str, Any]) -> None:
    decision_state.write_json(path, payload)


def _report_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _section_hashes(lines: list[str]) -> dict[str, str]:
    return {key: value["hash"] for key, value in markdown_sections(lines).items()}


def _normalise(value: Any) -> str:
    return _PUNCT_RE.sub("", decision_state.compact(value)).lower()


def _price_family(rule: dict[str, Any]) -> str:
    condition = _NUMBER_RE.sub("#", _normalise(rule.get("condition")))
    return condition if _PRICE_WORD_RE.search(condition) else ""


def _fact_signature(rule: dict[str, Any]) -> tuple[Any, ...]:
    try:
        return decision_rule_extractor._fact_signature(decision_state.compact(rule.get("condition")))
    except AttributeError:
        return ((), (), (), ())


def _match_score(old: dict[str, Any], candidate: dict[str, Any]) -> int:
    """Score whether two Rule records represent the same investment logic."""
    if old.get("rule_id") and old.get("rule_id") == candidate.get("rule_id"):
        return 100
    score = 0
    if old.get("rule_scope") == candidate.get("rule_scope"):
        score += 20
    if old.get("source_section") == candidate.get("source_section"):
        score += 12
    if old.get("source_section_hash") == candidate.get("source_section_hash"):
        score += 12
    if old.get("action") == candidate.get("action"):
        score += 8
    if old.get("type") == candidate.get("type"):
        score += 5

    old_text = _normalise(old.get("condition"))
    new_text = _normalise(candidate.get("condition"))
    if old_text == new_text:
        return score + 50

    old_price, new_price = _price_family(old), _price_family(candidate)
    if old_price and old_price == new_price:
        return score + 48

    old_atoms, old_numbers, old_directions, old_named = _fact_signature(old)
    new_atoms, new_numbers, new_directions, new_named = _fact_signature(candidate)
    if old_atoms and old_atoms == new_atoms and old_directions == new_directions and old_named == new_named:
        # Numbers are intentionally ignored here: a threshold change is an
        # UPDATE of one Rule, not a new active Rule plus a stale old Rule.
        return score + 45
    return 0


def _logic_changed(old: dict[str, Any], new: dict[str, Any]) -> bool:
    fields = (
        "type",
        "condition",
        "operator",
        "min",
        "max",
        "currency",
        "action",
        "automation",
        "needs_review",
        "rule_scope",
    )
    return any(old.get(field) != new.get(field) for field in fields)


def _annotate_rule(rule: dict[str, Any], report_path: Path, lines: list[str], timestamp: str) -> dict[str, Any]:
    result = copy.deepcopy(rule)
    result.update(
        source_metadata_for_excerpt(
            report_path,
            lines,
            result.get("source_excerpt"),
            result.get("condition", ""),
        )
    )
    result.setdefault("active", True)
    result.setdefault("created_at", timestamp)
    result.setdefault("updated_at", timestamp)
    result["last_verified_at"] = timestamp
    return result


def _summary(company: dict[str, Any]) -> dict[str, Any]:
    active_rules = [rule for rule in company.get("rules", []) if rule.get("active", True) is not False]
    return {
        "total": len(active_rules),
        "entry": sum(rule.get("rule_scope") == "entry" for rule in active_rules),
        "validation": sum(rule.get("rule_scope") == "validation" for rule in active_rules),
        "redline": sum(rule.get("rule_scope") == "redline" for rule in active_rules),
        "monitoring_metric_count": len(company.get("monitoring_metrics") or []),
        "semantic_review_candidate_count": len(company.get("semantic_review_candidates") or []),
        "retired_rule_count": sum(rule.get("active", True) is False for rule in company.get("rules", [])),
    }


def _report_context(decision: dict[str, Any], root: Path) -> tuple[Path | None, list[str], str | None, dict[str, str]]:
    report_value = decision.get("report_path")
    if not report_value:
        return None, [], None, {}
    report_path = (root / str(report_value)).resolve()
    if not report_path.is_file() or root not in report_path.parents:
        return report_path, [], None, {}
    lines = _report_lines(report_path)
    return report_path, lines, canonical_file_sha256(report_path), _section_hashes(lines)


def _changed_sections(previous: dict[str, Any], current: dict[str, str], report_changed: bool) -> set[str]:
    old = previous.get("section_hashes") or {}
    if not old:
        return set(current)
    changed = {key for key in set(old) | set(current) if old.get(key) != current.get(key)}
    # A report with no headings, or a conversion from headed to unheaded text,
    # has one conservative whole-document binding.
    if report_changed and (not current or not old):
        changed.add("__whole_report__")
    return changed


def _rule_is_affected(rule: dict[str, Any], changed_hashes: set[str], report_changed: bool) -> bool:
    if not report_changed:
        return False
    # No line binding means the legacy structured field fell back to the
    # whole-report hash; review it conservatively on any report change.
    if rule.get("source_line_start") is None:
        return True
    section_hash = rule.get("source_section_hash")
    return not section_hash or section_hash in changed_hashes or "__whole_report__" in changed_hashes


def _candidate_is_affected(rule: dict[str, Any], changed_hashes: set[str]) -> bool:
    if rule.get("source_line_start") is None:
        return True
    section_hash = rule.get("source_section_hash")
    return not section_hash or section_hash in changed_hashes or "__whole_report__" in changed_hashes


def _explicit_retirement_candidate(
    old: dict[str, Any],
    candidates: list[dict[str, Any]],
    extracted: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Return an explicit superseding Rule or manual retirement confirmation."""
    old_id = str(old.get("rule_id") or "")
    confirmed = {
        str(value)
        for value in (extracted.get("retirement_confirmed_rule_ids") or [])
        if value
    }
    if old_id and (old_id in confirmed or old.get("retirement_confirmed") is True):
        return None, "retirement explicitly confirmed"
    for candidate in candidates:
        references: list[Any] = []
        for key in ("supersedes_rule_id", "superseded_rule_id", "supersedes"):
            value = candidate.get(key)
            references.extend(value if isinstance(value, list) else [value] if value else [])
        if old_id and old_id in {str(value) for value in references}:
            return str(candidate.get("rule_id") or ""), "replaced by an explicit superseding Rule"
    return None, None


def _change_entry(
    ticker: str,
    action: str,
    rule_id: str,
    reason: str,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "date": timestamp,
        "ticker": ticker,
        "action": action,
        "rule_id": rule_id,
        "reason": reason,
        "old_summary": (old or {}).get("condition"),
        "new_summary": (new or {}).get("condition"),
        "old_source_hash": (old or {}).get("source_hash"),
        "new_source_hash": (new or {}).get("source_hash"),
    }


def _bootstrap_company(
    company: dict[str, Any],
    report_path: Path | None,
    lines: list[str],
    timestamp: str,
) -> tuple[dict[str, Any], dict[str, int], list[dict[str, Any]]]:
    actions = Counter()
    changes: list[dict[str, Any]] = []
    for rule in company.get("rules", []):
        if report_path is not None:
            rule.update(_annotate_rule(rule, report_path, lines, timestamp))
        rule.setdefault("active", True)
        rule.setdefault("created_at", timestamp)
        rule.setdefault("updated_at", timestamp)
        rule["last_verified_at"] = timestamp
        if rule.get("active", True) is not False:
            actions["KEEP"] += 1
    company["summary"] = _summary(company)
    return company, dict(actions), changes


def _sync_changed_company(
    company: dict[str, Any],
    extracted: dict[str, Any],
    report_path: Path,
    lines: list[str],
    changed_hashes: set[str],
    timestamp: str,
) -> tuple[dict[str, Any], Counter, list[dict[str, Any]], bool]:
    old_rules = [copy.deepcopy(rule) for rule in company.get("rules", [])]
    candidates = [
        _annotate_rule(rule, report_path, lines, timestamp)
        for rule in extracted.get("rules", [])
        if _candidate_is_affected(rule, changed_hashes)
    ]
    unresolved = extracted.get("rule_extraction_status") == "extraction_failed" or (
        not extracted.get("rules") and bool(extracted.get("semantic_review_candidates"))
    )
    if unresolved:
        kept = []
        for rule in old_rules:
            retained = _annotate_rule(rule, report_path, lines, timestamp)
            if retained.get("active", True) is not False:
                retained["active"] = True
                retained["needs_review"] = True
                retained["retirement_status"] = "pending_retire"
                retained["retirement_reason"] = "semantic extraction unresolved after a report change"
            kept.append(retained)
        company["rules"] = kept
        company["summary"] = _summary(company)
        return company, Counter({"KEEP": sum(rule.get("active", True) is not False for rule in kept)}), [], True

    actions: Counter = Counter()
    changes: list[dict[str, Any]] = []
    used: set[int] = set()
    output: list[dict[str, Any]] = []
    pending_retire = False
    for old in old_rules:
        if old.get("active", True) is False:
            output.append(old)
            continue
        old_original = copy.deepcopy(old)
        if not _rule_is_affected(old_original, changed_hashes, True):
            output.append(_annotate_rule(old_original, report_path, lines, timestamp))
            actions["KEEP"] += 1
            continue
        ranked = sorted(
            ((score, index, candidate) for index, candidate in enumerate(candidates) if index not in used for score in [_match_score(old_original, candidate)] if score >= 45),
            key=lambda item: (-item[0], item[1]),
        )
        if ranked:
            _, index, candidate = ranked[0]
            used.add(index)
            merged = copy.deepcopy(candidate)
            merged["rule_id"] = old_original.get("rule_id") or merged.get("rule_id")
            merged["active"] = True
            merged["created_at"] = old_original.get("created_at") or timestamp
            merged["status"] = old_original.get("status", merged.get("status", "unknown"))
            merged["last_checked"] = old_original.get("last_checked", merged.get("last_checked"))
            action = "UPDATE" if _logic_changed(old_original, merged) else "KEEP"
            merged["updated_at"] = timestamp if action == "UPDATE" else old_original.get("updated_at", timestamp)
            merged["last_verified_at"] = timestamp
            output.append(merged)
            actions[action] += 1
            if action == "UPDATE":
                changes.append(_change_entry(company.get("ticker", ""), "UPDATE", old_original.get("rule_id", ""), "canonical report changed in the bound section", old_original, merged, timestamp))
            continue
        superseded_by, explicit_reason = _explicit_retirement_candidate(old_original, candidates, extracted)
        if explicit_reason:
            retired = copy.deepcopy(old_original)
            retired["active"] = False
            retired["retired_at"] = timestamp
            retired["retired_reason"] = explicit_reason
            retired["superseded_by"] = superseded_by
            retired["updated_at"] = timestamp
            output.append(retired)
            actions["RETIRE"] += 1
            changes.append(_change_entry(company.get("ticker", ""), "RETIRE", old.get("rule_id", ""), retired["retired_reason"], old, retired, timestamp))
            continue

        # Extractor miss is not evidence that the investment logic expired.
        # Keep every unmatched Rule active, especially redlines, and put it in
        # an explicit pending-retirement review queue until a person or an
        # explicit superseding Rule confirms retirement.
        pending = copy.deepcopy(old_original)
        pending["active"] = True
        pending["needs_review"] = True
        pending["retirement_status"] = "pending_retire"
        pending["retirement_reason"] = "extractor did not match the old Rule after a report change"
        pending["updated_at"] = timestamp
        pending["last_verified_at"] = timestamp
        output.append(pending)
        actions["KEEP"] += 1
        pending_retire = True

    for index, candidate in enumerate(candidates):
        if index in used:
            continue
        candidate["active"] = True
        candidate["created_at"] = timestamp
        candidate["updated_at"] = timestamp
        candidate["last_verified_at"] = timestamp
        candidate["status"] = "unknown"
        output.append(candidate)
        actions["ADD"] += 1
        changes.append(_change_entry(company.get("ticker", ""), "ADD", candidate.get("rule_id", ""), "new decision condition in the changed report section", None, candidate, timestamp))

    company["rules"] = output
    company["rule_extraction_status"] = extracted.get("rule_extraction_status") or company.get("rule_extraction_status")
    company["zero_rule_reason"] = extracted.get("zero_rule_reason")
    company["extraction_error"] = extracted.get("extraction_error")
    company["monitoring_metrics"] = extracted.get("monitoring_metrics") or company.get("monitoring_metrics") or []
    company["semantic_review_candidates"] = extracted.get("semantic_review_candidates") or company.get("semantic_review_candidates") or []
    company["summary"] = _summary(company)
    return company, actions, changes, pending_retire


def sync_decision_rules(
    repo_root: Path = ROOT,
    *,
    tickers: Iterable[str] | None = None,
    write: bool = False,
    rebuild_dashboard: bool = False,
) -> dict[str, Any]:
    """Synchronize only selected companies whose canonical report changed."""
    root = repo_root.resolve()
    data = root / "data" / "investment-dashboard"
    board = _load(data / "decision_board.json", {})
    decisions = [item for item in board.get("decisions", []) if isinstance(item, dict)]
    previous = _load(data / decision_state.RULES_RELATIVE.name, {})
    previous_companies = {
        decision_state.compact(item.get("ticker")).upper(): copy.deepcopy(item)
        for item in previous.get("companies", [])
        if isinstance(item, dict) and decision_state.compact(item.get("ticker"))
    }
    lifecycle_path = data / LIFECYCLE_RELATIVE.name
    lifecycle = _load(lifecycle_path, {"schema_version": 1, "companies": {}})
    lifecycle.setdefault("schema_version", 1)
    lifecycle.setdefault("companies", {})
    requested = {decision_state.compact(ticker).upper() for ticker in (tickers or []) if decision_state.compact(ticker)}
    timestamp = now_iso()
    action_counts: Counter = Counter()
    changes: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []
    touched: list[str] = []
    companies: list[dict[str, Any]] = []

    for decision in decisions:
        counts_before_company = action_counts.copy()
        ticker = decision_state.compact(decision.get("ticker")).upper()
        if requested and ticker not in requested:
            if ticker in previous_companies:
                companies.append(previous_companies[ticker])
            continue
        touched.append(ticker)
        old_company = previous_companies.get(ticker)
        report_path, lines, report_hash, section_hashes = _report_context(decision, root)
        if report_path is None or report_hash is None:
            if old_company:
                companies.append(old_company)
            manual_review.append({"ticker": ticker, "reason": "canonical_report_missing_or_unreadable"})
            continue
        previous_meta = lifecycle["companies"].get(ticker) or {}
        report_changed = bool(previous_meta.get("canonical_report_hash") and previous_meta.get("canonical_report_hash") != report_hash)
        if old_company is None:
            extracted = decision_rule_extractor.extract_company(decision, root)
            company = {
                "company_id": decision_state.company_id(decision),
                "company": decision.get("company"),
                "ticker": ticker,
                "market": decision.get("market") or "unknown",
                "realtime_scope": "supported" if decision.get("market") in decision_state.REALTIME_MARKETS else "research_only",
                "canonical_report": decision.get("report_path"),
                **extracted,
            }
            for rule in company["rules"]:
                rule["active"] = True
                rule["created_at"] = timestamp
                rule["updated_at"] = timestamp
                rule["last_verified_at"] = timestamp
                action_counts["ADD"] += 1
            company["summary"] = _summary(company)
        elif not previous_meta:
            company, counts, bootstrap_changes = _bootstrap_company(old_company, report_path, lines, timestamp)
            action_counts.update(counts)
            changes.extend(bootstrap_changes)
        elif not report_changed:
            company = copy.deepcopy(old_company)
            company["canonical_report"] = decision.get("report_path") or company.get("canonical_report")
            for rule in company.get("rules", []):
                if rule.get("active", True) is not False:
                    rule.update(_annotate_rule(rule, report_path, lines, timestamp))
                    action_counts["KEEP"] += 1
            company["summary"] = _summary(company)
        else:
            changed = _changed_sections(previous_meta, section_hashes, report_changed)
            extracted = decision_rule_extractor.extract_company(decision, root)
            old_section_hashes = previous_meta.get("section_hashes") or {}
            changed_hashes = {
                hashes[key]
                for hashes in (old_section_hashes, section_hashes)
                if isinstance(hashes, dict)
                for key in changed
                if key in hashes
            }
            if "__whole_report__" in changed:
                changed_hashes.add("__whole_report__")
            company, counts, company_changes, unresolved = _sync_changed_company(
                old_company,
                extracted,
                report_path,
                lines,
                changed_hashes or changed,
                timestamp,
            )
            action_counts.update(counts)
            changes.extend(company_changes)
            if unresolved:
                manual_review.append({"ticker": ticker, "reason": "semantic_extraction_unresolved; active rules retained"})
        lifecycle["companies"][ticker] = {
            "canonical_report": decision.get("report_path"),
            "canonical_report_hash": report_hash,
            "section_hashes": section_hashes,
            "last_sync_at": timestamp,
            "last_sync_actions": {
                action: action_counts.get(action, 0) - counts_before_company.get(action, 0)
                for action in RULE_ACTIONS
            },
        }
        companies.append(company)

    for ticker, company in previous_companies.items():
        if not requested and ticker not in {item.get("ticker") for item in companies}:
            companies.append(company)

    companies.sort(key=lambda item: item.get("ticker") or "")
    payload = copy.deepcopy(previous)
    payload.setdefault("schema_version", decision_state.SCHEMA_VERSION)
    payload["companies"] = companies
    payload["rule_count"] = sum(
        rule.get("active", True) is not False
        for company in companies
        for rule in company.get("rules", [])
    )
    payload["lifecycle_policy"] = {
        "active_rule_actions": list(RULE_ACTIONS),
        "source_binding": "rule source_text/source_hash + containing Markdown source_section_hash",
        "report_change_policy": "only Rules bound to changed source sections are rechecked",
        "price_change_policy": "quote changes update runtime status only; they never update Rule content",
        "event_policy": "Event Radar can request Drift but cannot mutate Rules directly",
    }

    change_log = _load(data / CHANGE_LOG_RELATIVE.name, {"schema_version": 1, "changes": [], "sync_runs": []})
    change_log.setdefault("schema_version", 1)
    change_log.setdefault("changes", [])
    change_log.setdefault("sync_runs", [])
    run = {
        "date": timestamp,
        "tickers": touched,
        "actions": {action: action_counts.get(action, 0) for action in RULE_ACTIONS},
        "manual_review": manual_review,
    }
    if write:
        change_log["changes"].extend(changes)
        change_log["sync_runs"].append(run)
        _write(data / decision_state.RULES_RELATIVE.name, decision_state.rule_definition_payload(payload))
        _write(lifecycle_path, lifecycle)
        _write(data / CHANGE_LOG_RELATIVE.name, change_log)
        if rebuild_dashboard:
            import build_investment_dashboard

            build_investment_dashboard.build_dashboard(root)
    return {
        "status": "written" if write else "dry_run",
        "company_count": len(companies),
        "rule_count": payload["rule_count"],
        "touched_tickers": touched,
        "actions": {action: action_counts.get(action, 0) for action in RULE_ACTIONS},
        "manual_review": manual_review,
        "changed_rule_count": sum(action_counts.get(action, 0) for action in ("UPDATE", "ADD", "RETIRE")),
        "outputs": [
            str(LIFECYCLE_RELATIVE),
            str(CHANGE_LOG_RELATIVE),
            str(decision_state.RULES_RELATIVE),
        ] if write else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--ticker", action="append", help="only synchronize this ticker; repeatable")
    parser.add_argument("--rebuild-dashboard", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = sync_decision_rules(
        args.repo_root,
        tickers=args.ticker,
        write=args.write,
        rebuild_dashboard=args.rebuild_dashboard,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
