#!/usr/bin/env python3
"""Audit canonical current-main-report ownership and produce migration artifacts.

Read-only by default. ``--write-artifacts`` writes the migration proposal and the
contract review list, never the canonical registry itself. Production report
selection must come from ``data/investment-dashboard/current_reports.json``.

Usage:
    python3 tools/audit_current_reports.py
    python3 tools/audit_current_reports.py --json
    python3 tools/audit_current_reports.py --write-artifacts
    python3 tools/audit_current_reports.py --require-canonical
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402
import current_reports  # noqa: E402


def load_context(root: Path, *, tracked_manifest: Path | None = None) -> dict[str, Any]:
    data_directory = root / "data" / "investment-dashboard"
    registry = dashboard.load_registry(root / "data" / "report-routing" / "company_registry.json")
    overrides = dashboard.load_json(
        data_directory / "overrides.json",
        {"schema_version": 1, "reports": {}, "companies": {}},
    )
    report_paths = sorted(
        (root / "reports").rglob("*.md"), key=lambda item: item.as_posix().casefold()
    )
    records = [
        record
        for report_path in report_paths
        if (record := dashboard.candidate_record(report_path, root, registry, overrides)) is not None
    ]
    resolutions = dashboard.load_main_report_resolutions(
        data_directory / "main_report_resolutions.json"
    )
    priorities = dashboard.reviewed_main_report_paths(resolutions, root)
    board = dashboard.load_json(data_directory / "decision_board.json", {})
    board_by_key = {
        f"{item.get('market')}:{str(item.get('ticker') or '').upper()}": item
        for item in board.get("decisions", [])
        if isinstance(item, dict)
    }
    canonical_payload = current_reports.load(
        data_directory / current_reports.FILENAME, strict=False
    )
    canonical_map = current_reports.mappings(canonical_payload)
    tracked = current_reports.tracked_paths(root, tracked_manifest)
    validation_errors: list[str] = []
    if canonical_payload:
        canonical_relative = (
            data_directory / current_reports.FILENAME
        ).relative_to(root).as_posix()
        if canonical_relative not in tracked:
            validation_errors.append(
                f"canonical registry is not a formal tracked asset: {canonical_relative}"
            )
        validation_errors.extend(current_reports.validate(
            canonical_payload,
            repo_root=root,
            registry=registry,
            records_by_path={str(record["report_path"]): record for record in records},
            tracked=tracked,
        ))
    fresh = dashboard.select_decisions(
        records,
        overrides,
        priority_report_paths=priorities,
        canonical_reports=canonical_map,
        exclude_unregistered=bool(canonical_map),
    )
    legacy_projection = {
        f"{decision.get('market')}:{str(decision.get('ticker') or '').upper()}": decision
        for decision in dashboard.select_decisions(
            records, overrides, priority_report_paths=priorities
        )
    }
    return {
        "root": root,
        "registry": registry,
        "records": records,
        "records_by_path": {str(record["report_path"]): record for record in records},
        "groups": dashboard.candidate_group_records(records),
        "board": board,
        "board_by_key": board_by_key,
        "legacy_projection": legacy_projection,
        "canonical_payload": canonical_payload,
        "canonical_map": canonical_map,
        "validation_errors": validation_errors,
        "tracked": tracked,
        "fresh": fresh,
    }


def candidate_flags(record: dict[str, Any], context: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if record.get("market") == "美股":
        flags.append("us_market")
    if not record.get("data_cutoff"):
        flags.append("cutoff_missing")
    if record.get("action") == "未提取":
        flags.append("action_not_extracted")
    if isinstance(record.get("decision_contract"), dict) and record.get("decision_contract"):
        contract_action = (record.get("decision_contract") or {}).get("action")
        lines = (context["root"] / str(record.get("report_path") or "")).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        body_section = dashboard.decision_section(lines)
        body_action = dashboard.classify_action(body_section) if body_section else "未提取"
        if contract_action and body_action not in {"未提取"} and body_action != contract_action:
            flags.append("contract_body_conflict")
    if record.get("valuation_section") and isinstance(record.get("valuation_section"), dict):
        source = record["valuation_section"].get("source_report_path")
        if source and source != record.get("report_path"):
            flags.append("mixed_source_valuation")
    if record.get("historical_price_reference"):
        flags.append("mixed_source_historical_price")
    return sorted(set(flags))


def identity_review(context: dict[str, Any]) -> dict[str, list[str]]:
    """Separate explicitly quarantined historical labels from unresolved identities."""
    blocked: dict[str, list[str]] = defaultdict(list)
    unresolved: dict[str, list[str]] = defaultdict(list)
    for record in context["records"]:
        ticker = str(record.get("ticker") or "").upper()
        company = str(record.get("company") or "")
        if not ticker:
            continue
        entry = dashboard.registry_company(context["registry"], company, ticker)
        if entry is None:
            continue
        allowed = {str(item).upper() for item in entry.get("tickers", [])}
        explicitly_blocked = {
            str(item).upper() for item in entry.get("blocked_tickers", [])
        }
        path = str(record.get("report_path") or "")
        if ticker in explicitly_blocked:
            blocked[ticker].append(path)
        elif allowed and ticker not in allowed:
            unresolved[ticker].append(path)
    return {
        "blocked": sorted({path for paths in blocked.values() for path in paths}),
        "unresolved": sorted({path for paths in unresolved.values() for path in paths}),
    }


def best_main_candidate(
    candidates: list[dict[str, Any]],
    *,
    valid_paths: set[str],
) -> dict[str, Any] | None:
    eligible = [
        record
        for record in candidates
        if str(record.get("report_path") or "") in valid_paths
        and dashboard.record_rank(record)[3] >= 2
    ]
    if not eligible:
        return None
    return sorted(eligible, key=dashboard.record_rank, reverse=True)[0]


def build_migration(context: dict[str, Any], *, ignore_registered: bool = False) -> dict[str, Any]:
    root = context["root"]
    records_by_path = context["records_by_path"]
    tracked = context["tracked"]
    registered_map = {} if ignore_registered else context["canonical_map"]
    valid_paths: set[str] = set()
    for path, record in records_by_path.items():
        if not (root / path).is_file() or path not in tracked:
            continue
        if dashboard.is_post_buy_tracking_report(record):
            continue
        if dashboard.is_role_subreport_path(path):
            continue
        if record.get("ticker") and record.get("market") in {"A股", "港股", "美股"}:
            valid_paths.add(path)
    companies: dict[str, Any] = {}
    requires_manual_review: list[dict[str, Any]] = []
    for key, candidates in sorted(context["groups"].items()):
        ticker = key.split(":", 1)[1]
        board_decision = context["board_by_key"].get(key, {})
        if ignore_registered:
            legacy_decision = context["legacy_projection"].get(key) or {}
            board_report = str(legacy_decision.get("report_path") or board_decision.get("report_path") or "")
        else:
            board_report = str(board_decision.get("report_path") or "")
        registered = registered_map.get(ticker)
        chosen = next(
            (record for record in candidates if str(record.get("report_path")) == (registered or board_report)),
            None,
        )
        if registered:
            recommended = registered
            confidence = "canonical"
            reason = "already registered in current_reports.json"
        elif board_report and board_report in valid_paths:
            recommended = board_report
            confidence = "high"
            reason = "board current selection is a valid main report"
        else:
            best = best_main_candidate(candidates, valid_paths=valid_paths)
            recommended = str(best.get("report_path")) if best else None
            confidence = "medium" if best else "none"
            if best and board_report and dashboard.is_role_subreport_path(board_report):
                reason = f"replaces role sub-report {board_report}"
            elif best:
                reason = f"replaces unregistered/legacy selection {board_report or 'none'}"
            else:
                reason = "no validated main report candidate"
        flags = candidate_flags(chosen, context) if chosen else []
        if recommended is None:
            flags.append("requires_manual_review")
            requires_manual_review.append({"ticker": ticker, "company": board_decision.get("company"), "reason": reason})
        entry = {
            "company": board_decision.get("company") or (chosen or {}).get("company"),
            "market": key.split(":", 1)[0],
            "board_report": board_report or None,
            "candidate_reports": [
                {
                    "report_path": record.get("report_path"),
                    "data_cutoff": record.get("data_cutoff"),
                    "action": record.get("action"),
                    "kind_rank": dashboard.record_rank(record)[3],
                }
                for record in sorted(candidates, key=dashboard.record_rank, reverse=True)[:12]
            ],
            "recommended_canonical_report": recommended,
            "confidence": confidence,
            "reason": reason,
            "flags": flags,
        }
        companies[ticker] = entry
    extras = {
        key: [record.get("report_path") for record in candidates]
        for key, candidates in context["groups"].items()
        if key not in context["board_by_key"]
    }
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "companies": companies,
        "requires_manual_review": requires_manual_review,
        "unregistered_groups_excluded_from_board": extras,
    }


def build_contract_review(context: dict[str, Any]) -> dict[str, Any]:
    root = context["root"]
    records: list[dict[str, Any]] = []
    for key, candidates in sorted(context["groups"].items()):
        ticker = key.split(":", 1)[1]
        board_decision = context["board_by_key"].get(key, {})
        for record in candidates:
            contract = record.get("decision_contract") or {}
            contract_action = contract.get("action")
            if not contract_action:
                continue
            path = str(record.get("report_path") or "")
            lines = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            body_section = dashboard.decision_section(lines)
            body_action = dashboard.classify_action(body_section) if body_section else "未提取"
            if body_action in {"未提取"} or body_action == contract_action:
                continue
            excerpt = ""
            for line in body_section or []:
                text = dashboard.clean_markdown(line)
                if body_action in text and len(text) >= 8:
                    excerpt = text[:220]
                    break
            records.append(
                {
                    "ticker": ticker,
                    "company": board_decision.get("company") or record.get("company"),
                    "report_path": path,
                    "report_sha256": current_reports.file_sha256(root / path),
                    "is_current_canonical": context["canonical_map"].get(ticker) == path,
                    "contract_action": contract_action,
                    "body_action": body_action,
                    "classification": (
                        "REAL_CONFLICT"
                        if context["canonical_map"].get(ticker) == path
                        else "CONTRACT_STALE"
                    ),
                    "review_status": "pending",
                    "current_dashboard_action": board_decision.get("action"),
                    "primary_judgment_label": (board_decision.get("primary_judgment") or {}).get("label"),
                    "body_excerpt": excerpt,
                }
            )
    records.sort(key=lambda item: (item["ticker"], item["report_path"]))
    return {
        "schema_version": 1,
        "status": "CONTRACT_REVIEW_REQUIRED",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "note": "contract 与正文最终 action 冲突；不自动修改 report/contract/action guidance，等待人工确认。",
        "records": records,
    }


def summarize(context: dict[str, Any], migration: dict[str, Any], contract_review: dict[str, Any]) -> dict[str, Any]:
    canonical_map = context["canonical_map"]
    board_keys = set(context["board_by_key"])
    board_tickers = {key.split(":", 1)[1]: key for key in board_keys}
    canonical = sorted(key for ticker, key in board_tickers.items() if ticker in canonical_map)
    legacy = sorted(key for ticker, key in board_tickers.items() if ticker not in canonical_map)
    missing = [ticker for ticker, path in canonical_map.items() if not (context["root"] / path).is_file()]
    invalid_type = [
        ticker
        for ticker, path in canonical_map.items()
        if dashboard.is_role_subreport_path(path)
        or dashboard.is_post_buy_tracking_report({"report_path": path})
    ]
    canonical_selected = sorted(
        decision.get("ticker")
        for decision in context["fresh"]
        if decision.get("current_report_source") == "canonical"
    )
    ambiguous = [
        item["ticker"]
        for item in migration["requires_manual_review"]
    ]
    identities = identity_review(context)
    return {
        "companies": len(board_keys),
        "canonical": len(canonical),
        "legacy": len(legacy),
        "legacy_tickers": legacy,
        "canonical_selected": len(canonical_selected),
        "missing_report": len(missing),
        "ticker_mismatch": len(context["validation_errors"]),
        "invalid_report_type": len(invalid_type),
        "untracked": sum(
            1 for path in canonical_map.values() if path not in context["tracked"]
        ),
        "contract_review_required": len(contract_review["records"]),
        "ambiguous": len(ambiguous),
        "ambiguous_tickers": ambiguous,
        "validation_errors": context["validation_errors"],
        "identity_conflict": len(identities["unresolved"]),
        "identity_quarantined": len(identities["blocked"]),
        "identity_unresolved_paths": identities["unresolved"],
        "identity_quarantined_paths": identities["blocked"],
        "unregistered_groups_excluded_from_board": migration["unregistered_groups_excluded_from_board"],
        "requires_manual_review": migration["requires_manual_review"],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def render(summary: dict[str, Any], contract_review: dict[str, Any], migration: dict[str, Any]) -> str:
    lines = [
        "Canonical Current Report Audit",
        "",
        f"companies={summary['companies']}",
        f"canonical={summary['canonical']}",
        f"legacy={summary['legacy']}",
        "",
        f"missing report={summary['missing_report']}",
        f"ticker mismatch={summary['ticker_mismatch']}",
        f"invalid report type={summary['invalid_report_type']}",
        f"untracked={summary['untracked']}",
        f"contract review required={summary['contract_review_required']}",
        f"ambiguous={summary['ambiguous']}",
        f"identity conflict={summary['identity_conflict']}",
        f"identity quarantined={summary['identity_quarantined']}",
    ]
    if summary["legacy_tickers"]:
        lines.extend(["", "LEGACY (no canonical entry):", "  " + ", ".join(summary["legacy_tickers"])])
    if summary["validation_errors"]:
        lines.extend(["", "CANONICAL VALIDATION ERRORS:", *[f"  {item}" for item in summary["validation_errors"]]])
    if contract_review["records"]:
        lines.extend(["", f"CONTRACT_REVIEW_REQUIRED ({len(contract_review['records'])}):"])
        for item in contract_review["records"][:40]:
            lines.append(
                f"  {item['ticker']} {item['company']} | contract={item['contract_action']} vs body={item['body_action']}"
                f" | dashboard={item['current_dashboard_action']} | {item['report_path']}"
            )
    review = migration.get("requires_manual_review") or []
    if review:
        lines.extend(["", f"REQUIRES_MANUAL_REVIEW ({len(review)}):"])
        for item in review:
            lines.append(f"  {item['ticker']} {item.get('company')} | {item['reason']}")
    extras = summary["unregistered_groups_excluded_from_board"]
    if extras:
        lines.extend(["", "UNREGISTERED GROUPS EXCLUDED FROM BOARD:"])
        for key, paths in extras.items():
            lines.append(f"  {key} | candidate_count={len(paths)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-artifacts", action="store_true", help="write migration and contract review JSON files")
    parser.add_argument(
        "--proposal",
        action="store_true",
        help="compute migration recommendations without consulting the current canonical registry",
    )
    parser.add_argument("--require-canonical", action="store_true", help="fail when any company lacks canonical ownership")
    parser.add_argument(
        "--tracked-assets-manifest",
        type=Path,
        default=None,
        help="Use a source-checkout tracked asset manifest in a release without .git.",
    )
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    context = load_context(root, tracked_manifest=arguments.tracked_assets_manifest)
    migration = build_migration(context, ignore_registered=arguments.proposal)
    contract_review = build_contract_review(context)
    summary = summarize(context, migration, contract_review)
    if arguments.write_artifacts:
        data_directory = root / "data" / "investment-dashboard"
        write_json(data_directory / current_reports.MIGRATION_FILENAME, migration)
        write_json(data_directory / current_reports.CONTRACT_REVIEW_FILENAME, contract_review)
    payload = {"summary": summary, "migration": migration, "contract_review": contract_review}
    if arguments.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render(summary, contract_review, migration))
    if summary["validation_errors"] or summary["missing_report"]:
        return 1
    if summary["identity_conflict"]:
        return 1
    if arguments.require_canonical and summary["legacy"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
