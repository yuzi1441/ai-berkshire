#!/usr/bin/env python3
"""Read-only audit: do Markdown report conclusions reach structured dashboard data intact?

The tool re-parses the real report library with the production parser and
compares the result with the generated dashboard artifacts. It never writes
report, data, or site files. A HIGH finding makes the process exit non-zero.

Usage:
    python3 tools/audit_report_parsing.py
    python3 tools/audit_report_parsing.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402
import current_reports  # noqa: E402

SEVERITIES = ("HIGH", "MEDIUM", "LOW")
SUBREPORT_PATTERNS = re.compile(
    r"(?:^|/)(?:0[1-4]-[^/]*|[^/]*(?:财务估值分析|商业分析|行业竞争分析|风险管理层评估|巴菲特视角|芒格视角|李录视角|段永平视角)[^/]*)\.md$"
)
NON_MAIN_PATTERNS = re.compile(
    r"(checklist|technical-analysis|thesis(?:[-_]?tracker)?|drift|news(?:[-_]?pulse)?)",
    re.I,
)
QUARTER_END = {"03-31", "06-30", "09-30", "12-31"}
BUY_ACTIONS = {"买入", "分批买入"}
CONDITIONAL_ACTION_PATTERN = re.compile(
    r"(如果|若|假设|一旦|只有在|不建议|避免追高|市场认为|过去|曾经|持有现金)"
)
CURRENCY_TOKENS = (
    ("HKD", ("HK$", "港元", "港币")),
    ("USD", ("US$", "美元")),
    ("CNY", ("人民币", "CN¥", "¥", "￥")),
)
EXPECTED_CURRENCY = {"A股": "CNY", "港股": "HKD", "美股": "USD"}


class Audit:
    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []

    def add(
        self,
        severity: str,
        code: str,
        *,
        company: str | None = None,
        ticker: str | None = None,
        report: str | None = None,
        detail: str = "",
        evidence: Any = None,
        source: str | None = None,
    ) -> None:
        assert severity in SEVERITIES, severity
        finding = {
            "severity": severity,
            "code": code,
            "company": company,
            "ticker": ticker,
            "report_path": report,
            "source": source,
            "detail": detail,
        }
        if evidence is not None:
            finding["evidence"] = evidence
        self.findings.append(finding)

    def counts(self) -> dict[str, int]:
        result = {severity: 0 for severity in SEVERITIES}
        for finding in self.findings:
            result[finding["severity"]] += 1
        return result


def load_context(root: Path) -> dict[str, Any]:
    data_directory = root / "data" / "investment-dashboard"
    registry = dashboard.load_registry(root / "data" / "report-routing" / "company_registry.json")
    overrides = dashboard.load_json(
        data_directory / "overrides.json",
        {"schema_version": 1, "reports": {}, "companies": {}},
    )
    report_paths = sorted((root / "reports").rglob("*.md"), key=lambda item: item.as_posix().casefold())
    records = [
        record
        for report_path in report_paths
        if (record := dashboard.candidate_record(report_path, root, registry, overrides)) is not None
    ]
    checklist_records = [
        record
        for report_path in report_paths
        if (record := dashboard.checklist_record(report_path, root, registry)) is not None
    ]
    resolutions = dashboard.load_main_report_resolutions(data_directory / "main_report_resolutions.json")
    priorities = dashboard.reviewed_main_report_paths(resolutions, root)
    canonical_payload = current_reports.load(
        data_directory / current_reports.FILENAME, strict=False
    )
    canonical_map = current_reports.mappings(canonical_payload)
    fresh_decisions = dashboard.select_decisions(
        records,
        overrides,
        priority_report_paths=priorities,
        canonical_reports=canonical_map,
        legacy_tickers=current_reports.legacy_allowlist(canonical_payload),
        exclude_unregistered=bool(canonical_map),
    )

    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        ticker = str(record.get("ticker") or "").upper()
        market = str(record.get("market") or "")
        if (
            dashboard.is_company_equity(record)
            and not dashboard.is_post_buy_tracking_report(record)
            and ticker
            and market in {"A股", "港股", "美股"}
        ):
            groups[f"{market}:{ticker}"].append(record)

    return {
        "root": root,
        "registry": registry,
        "overrides": overrides,
        "records": records,
        "records_by_path": {str(record["report_path"]): record for record in records},
        "checklist_records": checklist_records,
        "fresh_decisions": fresh_decisions,
        "fresh_by_key": {
            f"{decision['market']}:{str(decision['ticker']).upper()}": decision
            for decision in fresh_decisions
        },
        "groups": groups,
        "board": dashboard.load_json(data_directory / "decision_board.json", {}),
        "board_by_key": {
            f"{decision.get('market')}:{str(decision.get('ticker') or '').upper()}": decision
            for decision in dashboard.load_json(data_directory / "decision_board.json", {}).get("decisions", [])
            if isinstance(decision, dict)
        },
        "catalog": dashboard.load_json(data_directory / "reports_catalog.json", {}),
        "company_state": dashboard.load_json(data_directory / "company_state.json", {}),
        "checklist_states": dashboard.load_json(data_directory / "checklist_states.json", {}),
        "decision_rules": dashboard.load_json(data_directory / "decision_rules.json", {}),
        "report_history": dashboard.load_json(data_directory / "report_history.json", {}),
        "dashboard_core": dashboard.load_json(root / "site" / "data" / "dashboard_core.json", {}),
        "quotes": dashboard.load_json(data_directory / "quotes" / "latest.json", {}),
    }


def decision_key(decision: dict[str, Any]) -> str:
    return f"{decision.get('market')}:{str(decision.get('ticker') or '').upper()}"


def check_selection(audit: Audit, context: dict[str, Any]) -> None:
    board_decisions = context["board"].get("decisions") or []
    board_by_key: dict[str, dict[str, Any]] = {}
    for decision in board_decisions:
        key = decision_key(decision)
        if key in board_by_key:
            audit.add(
                "HIGH",
                "DUPLICATE_BOARD_TICKER",
                company=decision.get("company"),
                ticker=decision.get("ticker"),
                detail=f"同一 market:ticker 在 board 出现多次：{key}",
            )
            continue
        board_by_key[key] = decision
    fresh_by_key = context["fresh_by_key"]
    for key, board_decision in board_by_key.items():
        fresh = fresh_by_key.get(key)
        if fresh is None:
            audit.add(
                "HIGH",
                "SELECTION_BOARD_EXTRA",
                company=board_decision.get("company"),
                ticker=board_decision.get("ticker"),
                report=board_decision.get("report_path"),
                detail="board 中存在当前 parser 无法选出的公司",
            )
            continue
        if board_decision.get("report_path") != fresh.get("report_path"):
            audit.add(
                "HIGH",
                "SELECTION_STALE",
                company=board_decision.get("company"),
                ticker=board_decision.get("ticker"),
                report=board_decision.get("report_path"),
                detail=f"board 选稿 {board_decision.get('report_path')} != 重算选稿 {fresh.get('report_path')}",
            )
    for key in fresh_by_key.keys() - board_by_key.keys():
        fresh = fresh_by_key[key]
        audit.add(
            "HIGH",
            "SELECTION_BOARD_MISSING",
            company=fresh.get("company"),
            ticker=fresh.get("ticker"),
            report=fresh.get("report_path"),
            detail="重算可选出公司但 board 缺失",
        )

    for key, fresh in fresh_by_key.items():
        path = str(fresh.get("report_path") or "")
        name = Path(path).name
        if dashboard.is_post_buy_tracking_report(fresh):
            audit.add(
                "HIGH",
                "SUBREPORT_SELECTED",
                company=fresh.get("company"),
                ticker=fresh.get("ticker"),
                report=path,
                detail="post-buy 类报告被选为当前主报告",
            )
            continue
        if NON_MAIN_PATTERNS.search(name):
            audit.add(
                "HIGH",
                "SUBREPORT_SELECTED",
                company=fresh.get("company"),
                ticker=fresh.get("ticker"),
                report=path,
                detail="非主报告类型（checklist/technical/thesis/drift/news）被选为当前主报告",
            )
        group = context["groups"].get(key, [])
        selected_rank = dashboard.record_rank(fresh)
        if SUBREPORT_PATTERNS.search(path):
            better = [
                record
                for record in group
                if dashboard.record_rank(record)[3] >= 4
                and (record.get("data_cutoff") or "") >= (fresh.get("data_cutoff") or "")
            ]
            severity = "HIGH" if better else "MEDIUM"
            audit.add(
                severity,
                "SUBREPORT_SELECTED",
                company=fresh.get("company"),
                ticker=fresh.get("ticker"),
                report=path,
                detail=(
                    "角色/专题子报告被选为当前主报告"
                    + (f"；同截止日存在完整报告：{[r['report_path'] for r in better][:3]}" if better else "；无同截止日完整报告")
                ),
                evidence={"selected_rank": list(selected_rank)},
            )


def report_override_for(context: dict[str, Any], path: str | None) -> dict[str, Any]:
    entry = (context["overrides"].get("reports", {}) or {}).get(str(path or ""))
    return entry if isinstance(entry, dict) else {}


def company_override_for(context: dict[str, Any], company: str | None) -> dict[str, Any]:
    entry = (context["overrides"].get("companies", {}) or {}).get(str(company or ""))
    return entry if isinstance(entry, dict) else {}


def check_identity(audit: Audit, context: dict[str, Any]) -> None:
    registry = context["registry"]
    root = context["root"]
    seen_paths: dict[str, str] = {}
    registry_missing: list[str] = []
    for decision in context["fresh_decisions"]:
        company = str(decision.get("company") or "")
        ticker = str(decision.get("ticker") or "").upper()
        market = str(decision.get("market") or "")
        path = str(decision.get("report_path") or "")
        suffix = ticker.rsplit(".", 1)[-1] if "." in ticker else ""
        if market == "A股" and suffix not in {"SH", "SZ", "BJ"}:
            audit.add("HIGH", "TICKER_MARKET_MISMATCH", company=company, ticker=ticker, report=path, detail=f"A股 ticker 后缀异常：{ticker}")
        if market == "港股" and suffix != "HK":
            audit.add("HIGH", "TICKER_MARKET_MISMATCH", company=company, ticker=ticker, report=path, detail=f"港股 ticker 后缀异常：{ticker}")
        if market == "美股" and suffix in {"SH", "SZ", "BJ", "HK"}:
            audit.add("HIGH", "TICKER_MARKET_MISMATCH", company=company, ticker=ticker, report=path, detail=f"美股 ticker 使用了 A/H 后缀：{ticker}")
        if market in {"A股", "港股"}:
            derived_market = dashboard.market_for_ticker(ticker, None)
            if derived_market and derived_market != market:
                audit.add("HIGH", "MARKET_MISMATCH", company=company, ticker=ticker, report=path, detail=f"board market={market} 但 ticker 推导 market={derived_market}")
        entry = dashboard.registry_company(registry, company, ticker)
        if entry:
            tickers = {str(item).upper() for item in entry.get("tickers", [])}
            if tickers and ticker and ticker not in tickers:
                audit.add(
                    "MEDIUM",
                    "TICKER_REGISTRY_MISMATCH",
                    company=company,
                    ticker=ticker,
                    report=path,
                    detail=f"registry 中公司对应 tickers={sorted(tickers)}，当前 ticker={ticker}",
                )
            canonical = str(entry.get("canonical_name") or "")
            valid_names = {dashboard.normalize_company_name(canonical)}
            valid_names.update(dashboard.normalize_company_name(str(alias)) for alias in entry.get("aliases", []))
            valid_names.discard("")
            if valid_names and dashboard.normalize_company_name(company) not in valid_names:
                audit.add("LOW", "ALIAS_NAME", company=company, ticker=ticker, report=path, detail=f"registry canonical={canonical}")
        else:
            registry_missing.append(f"{company}({ticker})")
        entity_directory = str(decision.get("entity_directory") or "")
        if entity_directory and not (root / "reports" / entity_directory).is_dir():
            audit.add("MEDIUM", "ENTITY_DIRECTORY_MISSING", company=company, ticker=ticker, report=path, detail=f"entity_directory 不存在：reports/{entity_directory}")
        if not (root / path).is_file():
            audit.add("HIGH", "BROKEN_REPORT_PATH", company=company, ticker=ticker, report=path, detail="当前主报告文件不存在")
        if path in seen_paths and seen_paths[path] != decision_key(decision):
            audit.add("HIGH", "REPORT_PATH_DUPLICATED", company=company, ticker=ticker, report=path, detail=f"同一路径被多个公司使用：{seen_paths[path]} 与 {decision_key(decision)}")
        seen_paths[path] = decision_key(decision)
        name = Path(path).name
        if name.lower() in {"readme.md", "moc.md"}:
            audit.add("HIGH", "SUBREPORT_SELECTED", company=company, ticker=ticker, report=path, detail="README/MOC 不应成为主报告")
    if registry_missing:
        audit.add(
            "LOW",
            "REGISTRY_MISSING",
            detail=f"registry 无匹配条目的当前主报告公司 {len(registry_missing)} 家（前 10）：{registry_missing[:10]}",
        )


def check_cutoff(audit: Audit, context: dict[str, Any]) -> None:
    root = context["root"]
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        board_decision = context["board_by_key"].get(decision_key(decision), {})
        cutoff = decision.get("data_cutoff")
        board_cutoff = board_decision.get("data_cutoff")
        if cutoff != board_cutoff:
            audit.add(
                "HIGH",
                "CUTOFF_STALE",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"重算 cutoff={cutoff} != board cutoff={board_cutoff}",
            )
        if not cutoff:
            audit.add("MEDIUM", "CUTOFF_MISSING", company=company, ticker=ticker, report=path, detail="当前主报告没有明确数据截止日")
            continue
        if cutoff[5:] in QUARTER_END:
            financial_market = dashboard.extract_market_data_cutoff(
                (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            )
            if financial_market and financial_market != cutoff:
                audit.add(
                    "MEDIUM",
                    "FINANCIAL_PERIOD_CUTOFF",
                    company=company,
                    ticker=ticker,
                    report=path,
                    detail=f"cutoff={cutoff} 疑似财务期末，行情截止={financial_market}",
                )
        completed = decision.get("report_completed_at")
        if completed and completed < cutoff:
            audit.add(
                "MEDIUM",
                "COMPLETED_BEFORE_CUTOFF",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"报告完成日 {completed} 早于数据截止日 {cutoff}",
            )
        contract = decision.get("decision_contract") or {}
        contract_cutoff = contract.get("data_cutoff")
        if contract_cutoff and contract_cutoff != cutoff:
            audit.add(
                "LOW",
                "CONTRACT_CUTOFF_OVERRIDDEN",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"contract data_cutoff={contract_cutoff}，采用正文解析值={cutoff}",
                evidence={"contract_cutoff": contract_cutoff, "resolved_cutoff": cutoff},
            )
        lines = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
        same_line = [
            line
            for line in lines[:40]
            if ("研究日期" in line or "报告日期" in line)
            and ("数据截止" in line or "行情基准" in line or "数据截至" in line)
        ]
        for line in same_line:
            dates = re.findall(r"20\d{2}[-./年]\d{1,2}[-./月]\d{1,2}", line)
            if len(set(dates)) > 1 and cutoff not in line:
                audit.add(
                    "MEDIUM",
                    "CUTOFF_MULTI_DATE_LINE",
                    company=company,
                    ticker=ticker,
                    report=path,
                    detail=f"同行多日期但解析值未出现在该行：{line.strip()[:120]}",
                )


def ref_price_expected_currency(market: str | None) -> str | None:
    return EXPECTED_CURRENCY.get(str(market or ""))


def check_reference_price(audit: Audit, context: dict[str, Any]) -> None:
    root = context["root"]
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        reference = decision.get("report_reference_price")
        board_reference = (context["board_by_key"].get(decision_key(decision), {}) or {}).get("report_reference_price")
        board_price = (board_reference or {}).get("price")
        price = (reference or {}).get("price")
        if price != board_price:
            audit.add(
                "HIGH",
                "REFERENCE_PRICE_STALE",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"重算 reference={price} != board reference={board_price}",
            )
        if not reference:
            continue
        if not isinstance(price, (int, float)) or price <= 0 or price >= 1_000_000:
            audit.add("HIGH", "REFERENCE_PRICE_RANGE", company=company, ticker=ticker, report=path, detail=f"异常 reference={price}")
            continue
        expected = ref_price_expected_currency(decision.get("market"))
        if (reference.get("currency") or "").upper() != expected:
            audit.add(
                "HIGH",
                "REFERENCE_PRICE_CURRENCY",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"reference 币种 {reference.get('currency')} != 市场预期 {expected}",
            )
        line_number = reference.get("line")
        lines = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
        if not isinstance(line_number, int) or not (1 <= line_number <= len(lines)):
            audit.add("MEDIUM", "REFERENCE_PRICE_LINE", company=company, ticker=ticker, report=path, detail=f"line={line_number} 超出范围")
            continue
        line = lines[line_number - 1]
        raw = f"{price:g}"
        comma = f"{price:,.2f}".rstrip("0").rstrip(".")
        compact = line.replace(",", "")
        if raw not in line and comma not in line and raw not in compact:
            audit.add(
                "MEDIUM",
                "REFERENCE_PRICE_LINE_EVIDENCE",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"line {line_number} 未找到解析值 {raw}",
                evidence={"line": line.strip()[:160]},
            )


def check_action(audit: Audit, context: dict[str, Any]) -> None:
    root = context["root"]
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        action = decision.get("action")
        board_action = (context["board_by_key"].get(decision_key(decision), {}) or {}).get("action")
        if action != board_action:
            audit.add(
                "HIGH",
                "ACTION_STALE",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"重算 action={action} != board action={board_action}",
            )
        contract = decision.get("decision_contract") or {}
        contract_action = contract.get("action")
        report_override = report_override_for(context, path)
        manual_override = report_override.get("action") or company_override_for(context, company).get("action")
        if contract_action and contract_action != action and not manual_override:
            audit.add(
                "HIGH",
                "ACTION_CONTRACT_MISMATCH",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"contract action={contract_action} 但解析 action={action}",
            )
        if contract_action and manual_override and contract_action != action:
            audit.add(
                "LOW",
                "ACTION_OVERRIDDEN_BY_HUMAN",
                company=company,
                ticker=ticker,
                report=path,
                detail=f"contract action={contract_action} 被 overrides 覆盖为 {action}",
            )
        if action == "未提取":
            audit.add(
                "MEDIUM",
                "ACTION_NOT_EXTRACTED",
                company=company,
                ticker=ticker,
                report=path,
                detail="当前主报告未解析出明确 action",
            )
            continue
        if action in BUY_ACTIONS and not contract_action:
            lines = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            section = dashboard.decision_section(lines) or lines[-160:]
            for line in section:
                text = dashboard.clean_markdown(line)
                if action in text and CONDITIONAL_ACTION_PATTERN.search(text):
                    audit.add(
                        "LOW",
                        "ACTION_HEURISTIC_RISK",
                        company=company,
                        ticker=ticker,
                        report=path,
                        detail=f"heuristic action={action}，所在句含条件/否定词",
                        evidence={"line": text[:160]},
                    )
                    break


def check_stances(audit: Audit, context: dict[str, Any]) -> None:
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        stances = decision.get("investor_stances") or []
        board_stances = (context["board_by_key"].get(decision_key(decision), {}) or {}).get("investor_stances") or []
        if json.dumps(stances, ensure_ascii=False, sort_keys=True) != json.dumps(board_stances, ensure_ascii=False, sort_keys=True):
            audit.add(
                "HIGH",
                "STANCE_STALE",
                company=company,
                ticker=ticker,
                report=path,
                detail="重算 investor_stances != board investor_stances",
            )
        seen: set[str] = set()
        expected = ref_price_expected_currency(decision.get("market"))
        for stance in stances:
            if not isinstance(stance, dict):
                continue
            label = str(stance.get("stance") or "")
            if label in seen:
                audit.add("MEDIUM", "STANCE_DUPLICATE", company=company, ticker=ticker, report=path, detail=f"stance 重复：{label}")
            seen.add(label)
            if label not in {"激进型", "稳健型", "保守型"}:
                audit.add("MEDIUM", "STANCE_LABEL", company=company, ticker=ticker, report=path, detail=f"未知 stance 标签：{label}")
            price_range = str(stance.get("price_range") or "")
            for currency, tokens in CURRENCY_TOKENS:
                if any(token in price_range for token in tokens) and currency != expected:
                    audit.add(
                        "MEDIUM",
                        "STANCE_CURRENCY",
                        company=company,
                        ticker=ticker,
                        report=path,
                        detail=f"{label} 价格区间 {price_range} 币种({currency})与市场({expected})不符",
                    )
        contract = decision.get("decision_contract") or {}
        contract_stances = contract.get("investor_stances") or []
        if contract_stances and stances:
            contract_map = {
                str(item.get("stance") or ""): str(item.get("action") or "")
                for item in contract_stances
                if isinstance(item, dict)
            }
            parsed_map = {
                str(item.get("stance") or ""): str(item.get("action") or "")
                for item in stances
                if isinstance(item, dict)
            }
            differences = {
                key: (contract_map.get(key), parsed_map.get(key))
                for key in set(contract_map) | set(parsed_map)
                if contract_map.get(key) != parsed_map.get(key)
            }
            if differences:
                audit.add(
                    "LOW",
                    "STANCE_CONTRACT_BODY_DIFF",
                    company=company,
                    ticker=ticker,
                    report=path,
                    detail="contract 与正文 stance action 不一致（contract 为权威）",
                    evidence=differences,
                )


def _range_bounds(value: str) -> tuple[float, float] | None:
    match = re.search(
        r"(?<![\d,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*[-—–~至]\s*"
        r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?!\d)",
        value,
    )
    if not match:
        return None
    return float(match.group(1).replace(",", "")), float(match.group(2).replace(",", ""))


def check_price_plan(audit: Audit, context: dict[str, Any]) -> None:
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        plan = decision.get("price_plan") or []
        board = context["board_by_key"].get(decision_key(decision), {}) or {}
        board_plan = board.get("price_plan") or []
        if json.dumps(plan, ensure_ascii=False, sort_keys=True) != json.dumps(board_plan, ensure_ascii=False, sort_keys=True):
            audit.add("HIGH", "PRICE_PLAN_STALE", company=company, ticker=ticker, report=path, detail="重算 price_plan != board price_plan")
        expected = ref_price_expected_currency(decision.get("market"))
        for row in plan:
            if not isinstance(row, dict):
                continue
            price_range = str(row.get("price_range") or "")
            action = str(row.get("action") or "")
            for currency, tokens in CURRENCY_TOKENS:
                if any(token in price_range for token in tokens) and currency != expected:
                    audit.add(
                        "MEDIUM",
                        "PRICE_PLAN_CURRENCY",
                        company=company,
                        ticker=ticker,
                        report=path,
                        detail=f"price_plan {price_range} 币种({currency})与市场({expected})不符",
                    )
            bounds = _range_bounds(price_range)
            if bounds and bounds[0] > bounds[1]:
                audit.add("MEDIUM", "PRICE_RANGE_REVERSED", company=company, ticker=ticker, report=path, detail=f"价格区间上下界颠倒：{price_range}")
            if action and re.search(r"买入|建仓|分批", action) and re.search(r"不低于|高于|≥|>=", price_range):
                audit.add("LOW", "PRICE_PLAN_FLOOR_BUY", company=company, ticker=ticker, report=path, detail=f"买入动作配下限区间：{action} {price_range}")
        buy_price = decision.get("buy_price")
        board_buy = board.get("buy_price")
        if buy_price != board_buy:
            audit.add("HIGH", "BUY_PRICE_STALE", company=company, ticker=ticker, report=path, detail=f"重算 buy={buy_price} != board buy={board_buy}")


def check_scenario(audit: Audit, context: dict[str, Any]) -> None:
    pollution = re.compile(r"亿|万亿|万|%|％|倍|GMV|CAGR|收入|利润|净利|EPS|EBITDA|市值|margin", re.I)
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        scenarios = decision.get("scenario_valuation") or []
        board = context["board_by_key"].get(decision_key(decision), {}) or {}
        board_scenarios = board.get("scenario_valuation") or []
        if json.dumps(scenarios, ensure_ascii=False, sort_keys=True) != json.dumps(board_scenarios, ensure_ascii=False, sort_keys=True):
            audit.add("HIGH", "SCENARIO_STALE", company=company, ticker=ticker, report=path, detail="重算 scenario_valuation != board scenario_valuation")
        for entry in scenarios:
            target = str(entry.get("target_price") or "")
            if pollution.search(target):
                audit.add(
                    "HIGH",
                    "SCENARIO_POLLUTION",
                    company=company,
                    ticker=ticker,
                    report=path,
                    detail=f"scenario target 含非每股语义：{target}",
                )
            if not re.search(r"(元|港元|美元|HK\$|US\$|\$)", target, re.I):
                audit.add("LOW", "SCENARIO_UNIT", company=company, ticker=ticker, report=path, detail=f"scenario target 未带币种（可能由明确每股列推导）：{target}")


def latest_checklist_record(context: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any] | None:
    company = str(decision.get("company") or "")
    ticker = str(decision.get("ticker") or "").upper()
    candidates = [record for record in context["checklist_records"] if record.get("company") == company]
    if not candidates and ticker:
        candidates = [record for record in context["checklist_records"] if str(record.get("ticker") or "").upper() == ticker]
    if not candidates:
        return None
    return sorted(candidates, key=dashboard.checklist_rank, reverse=True)[0]


def check_checklist(audit: Audit, context: dict[str, Any]) -> None:
    root = context["root"]
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        board = context["board_by_key"].get(decision_key(decision), {}) or {}
        board_checklist = board.get("checklist") or {}
        fresh = latest_checklist_record(context, decision)
        if not fresh:
            if board_checklist.get("status") not in {None, "missing"}:
                audit.add("HIGH", "CHECKLIST_STALE", company=company, ticker=ticker, report=board.get("report_path"), detail="board 有 checklist 但重算无")
            continue
        if board_checklist.get("status") == "missing":
            continue
        for field in ("status", "passed_count", "total_gates", "report_path"):
            if fresh.get(field) != board_checklist.get(field):
                audit.add(
                    "HIGH",
                    "CHECKLIST_STALE",
                    company=company,
                    ticker=ticker,
                    report=fresh.get("report_path"),
                    detail=f"checklist {field}: 重算={fresh.get(field)} != board={board_checklist.get(field)}",
                )
        passed = fresh.get("passed_count")
        total = fresh.get("total_gates")
        if isinstance(passed, int) and isinstance(total, int):
            if passed > total:
                audit.add("HIGH", "CHECKLIST_PASSED_GT_TOTAL", company=company, ticker=ticker, report=fresh.get("report_path"), detail=f"{passed}>{total}")
            gates = fresh.get("gates") or []
            if total and len(gates) != total:
                audit.add(
                    "MEDIUM",
                    "CHECKLIST_GATES_INCOMPLETE",
                    company=company,
                    ticker=ticker,
                    report=fresh.get("report_path"),
                    detail=f"结构化 gates={len(gates)} 与 total={total} 不一致",
                )
        if fresh.get("hard_veto") is True and fresh.get("status") != "否决":
            audit.add("HIGH", "CHECKLIST_VETO_STATUS", company=company, ticker=ticker, report=fresh.get("report_path"), detail=f"hard_veto=true 但 status={fresh.get('status')}")
        report_path = str(fresh.get("report_path") or "")
        if report_path and report_path == decision.get("report_path"):
            audit.add("HIGH", "CHECKLIST_AS_MAIN", company=company, ticker=ticker, report=report_path, detail="Checklist 同时被选为主报告")


def check_contract(audit: Audit, context: dict[str, Any]) -> None:
    registry = context["registry"]
    root = context["root"]
    for decision in context["fresh_decisions"]:
        contract = decision.get("decision_contract")
        if not isinstance(contract, dict):
            continue
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        contract_company = str(contract.get("company") or "")
        if contract_company:
            valid_names = set()
            entry = dashboard.registry_company(registry, company, ticker)
            if entry:
                valid_names.add(dashboard.normalize_company_name(str(entry.get("canonical_name") or "")))
                valid_names.update(dashboard.normalize_company_name(str(alias)) for alias in entry.get("aliases", []))
            valid_names.add(dashboard.normalize_company_name(str(company)))
            valid_names.discard("")
            normalized_contract = dashboard.normalize_company_name(contract_company)
            matched = normalized_contract in valid_names or any(
                normalized_contract and (normalized_contract in name or name in normalized_contract)
                for name in valid_names
            )
            if not matched:
                audit.add("MEDIUM", "CONTRACT_IDENTITY", company=company, ticker=ticker, report=path, detail=f"contract company={contract_company}")
        if contract.get("ticker") and str(contract["ticker"]).upper() != str(ticker).upper():
            audit.add("HIGH", "CONTRACT_IDENTITY", company=company, ticker=ticker, report=path, detail=f"contract ticker={contract.get('ticker')}")
        if contract.get("market") and contract["market"] not in {"未识别"} and contract["market"] != decision.get("market"):
            audit.add("HIGH", "CONTRACT_IDENTITY", company=company, ticker=ticker, report=path, detail=f"contract market={contract.get('market')}")
        contract_action = contract.get("action")
        override = report_override_for(context, path).get("action") or company_override_for(context, company).get("action")
        if contract_action and str(contract_action) != str(decision.get("action")) and not override:
            audit.add("MEDIUM", "CONTRACT_ACTION_BODY_DIFF", company=company, ticker=ticker, report=path, detail=f"contract action={contract_action} vs parsed action={decision.get('action')}")
        if contract_action and not override:
            lines = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            body_section = dashboard.decision_section(lines)
            if body_section:
                body_action = dashboard.classify_action(body_section)
                if body_action not in {"未提取"} and body_action != contract_action:
                    audit.add(
                        "MEDIUM",
                        "CONTRACT_BODY_ACTION_DIVERGENCE",
                        company=company,
                        ticker=ticker,
                        report=path,
                        detail=f"contract action={contract_action} vs 正文结论 action={body_action}（contract 为权威，需人工确认哪边正确）",
                        evidence={"contract_action": contract_action, "body_action": body_action},
                    )


def check_mixed_source(audit: Audit, context: dict[str, Any]) -> None:
    root = context["root"]
    for decision in context["fresh_decisions"]:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        current_cutoff = decision.get("data_cutoff") or ""
        section = decision.get("valuation_section")
        if isinstance(section, dict) and section.get("source_report_path"):
            source = str(section["source_report_path"])
            source_record = context["records_by_path"].get(source, {})
            source_cutoff = str(source_record.get("data_cutoff") or "")
            direction = "older" if source_cutoff < current_cutoff else "same_or_newer"
            audit.add(
                "MEDIUM" if direction == "older" else "LOW",
                "MIXED_SOURCE_VALUATION",
                company=company,
                ticker=ticker,
                report=path,
                source=source,
                detail=f"估值原文来自另一报告（{direction}）：source_cutoff={source_cutoff or '未标注'} current_cutoff={current_cutoff or '未标注'}；source_note={'有' if section.get('source_note') else '无'}；UI未见渲染 source_note",
                evidence={"current_cutoff": current_cutoff, "source_cutoff": source_cutoff},
            )
        historical = decision.get("historical_price_reference")
        if isinstance(historical, dict) and historical.get("source_report_path") and historical["source_report_path"] != path:
            source = str(historical["source_report_path"])
            source_record = context["records_by_path"].get(source, {})
            source_cutoff = str(source_record.get("data_cutoff") or historical.get("source_data_cutoff") or "")
            direction = "older" if source_cutoff and source_cutoff < current_cutoff else "same_or_newer"
            audit.add(
                "LOW",
                "MIXED_SOURCE_HISTORICAL_PRICE",
                company=company,
                ticker=ticker,
                report=path,
                source=source,
                detail=f"历史价格参照来自另一报告（{direction}，display_only）：source_cutoff={source_cutoff or '未标注'} current_cutoff={current_cutoff or '未标注'}",
            )


def check_catalog(audit: Audit, context: dict[str, Any]) -> None:
    root = context["root"]
    catalog_records = context["catalog"].get("records") or []
    catalog_paths = {str(record.get("report_path") or "") for record in catalog_records}
    board_decisions = context["board"].get("decisions") or []
    for decision in board_decisions:
        path = str(decision.get("report_path") or "")
        if path and path not in catalog_paths:
            audit.add("HIGH", "CATALOG_MISSING_CURRENT", company=decision.get("company"), ticker=decision.get("ticker"), report=path, detail="当前主报告不在 reports_catalog")
    for record in catalog_records:
        path = str(record.get("report_path") or "")
        if not path:
            continue
        if not (root / path).is_file():
            audit.add("HIGH", "CATALOG_BROKEN_PATH", company=record.get("company"), ticker=record.get("ticker"), report=path, detail="catalog 引用的报告文件不存在")
        if any(part in dashboard.SKIPPED_PATH_PARTS for part in Path(path).parts):
            audit.add("MEDIUM", "CATALOG_IGNORED_PATH", company=record.get("company"), ticker=record.get("ticker"), report=path, detail="catalog 引用了 skipped/staging 路径")
        if not path.startswith("reports/"):
            audit.add("MEDIUM", "CATALOG_OUTSIDE_REPORTS", company=record.get("company"), ticker=record.get("ticker"), report=path, detail="catalog 路径不在 reports/ 下")
    raw_report_count = len(context["records"])
    if len(catalog_records) != raw_report_count:
        audit.add("MEDIUM", "CATALOG_COUNT_DRIFT", detail=f"catalog records={len(catalog_records)} 与重算候选={raw_report_count} 不一致")


def check_state_layers(audit: Audit, context: dict[str, Any]) -> None:
    board_decisions = context["board"].get("decisions") or []
    state_companies = {
        str(item.get("ticker") or "").upper(): item
        for item in (context["company_state"].get("companies") or [])
        if isinstance(item, dict)
    }
    for decision in board_decisions:
        ticker = str(decision.get("ticker") or "").upper()
        report_path = str(decision.get("report_path") or "")
        state = state_companies.get(ticker)
        if state is None:
            audit.add("HIGH", "STATE_MISSING", company=decision.get("company"), ticker=ticker, report=report_path, detail="company_state 缺少该公司")
            continue
        if str(state.get("canonical_report") or "") != report_path:
            audit.add(
                "HIGH",
                "STATE_CANONICAL_STALE",
                company=decision.get("company"),
                ticker=ticker,
                report=report_path,
                detail=f"company_state canonical_report={state.get('canonical_report')}",
            )
    checklist_companies = {
        str(item.get("ticker") or "").upper(): item
        for item in (context["checklist_states"].get("companies") or [])
        if isinstance(item, dict)
    }
    for decision in board_decisions:
        ticker = str(decision.get("ticker") or "").upper()
        board_checklist = decision.get("checklist") or {}
        if board_checklist.get("status") == "missing":
            continue
        state = checklist_companies.get(ticker)
        if state and board_checklist.get("report_path") and state.get("report_path") != board_checklist.get("report_path"):
            audit.add(
                "MEDIUM",
                "CHECKLIST_STATE_STALE",
                company=decision.get("company"),
                ticker=ticker,
                report=board_checklist.get("report_path"),
                detail=f"checklist_states report={state.get('report_path')}",
            )
    core = context["dashboard_core"] or {}
    core_state = {
        str(item.get("ticker") or "").upper()
        for item in ((core.get("companyState") or {}).get("companies") or [])
        if isinstance(item, dict)
    }
    board_tickers = {str(decision.get("ticker") or "").upper() for decision in board_decisions}
    if core_state and core_state != board_tickers:
        audit.add("HIGH", "CORE_POPULATION_MISMATCH", detail=f"dashboard_core companyState={len(core_state)} 与 board={len(board_tickers)} 不一致")
    rules_companies = {
        str(item.get("ticker") or "").upper(): item
        for item in (context["decision_rules"].get("companies") or [])
        if isinstance(item, dict)
    }
    for decision in board_decisions:
        ticker = str(decision.get("ticker") or "").upper()
        rules = rules_companies.get(ticker)
        if not rules:
            continue
        sources = {str(rule.get("source_report") or "") for rule in rules.get("rules") or [] if isinstance(rule, dict)}
        sources.discard("")
        stale_sources = {source for source in sources if source != decision.get("report_path")}
        if stale_sources and decision.get("report_path") in sources:
            audit.add(
                "LOW",
                "RULES_SOURCE_OLDER",
                company=decision.get("company"),
                ticker=ticker,
                report=decision.get("report_path"),
                detail=f"decision_rules 同时引用其他报告：{sorted(stale_sources)[:3]}",
            )


def check_history(audit: Audit, context: dict[str, Any]) -> None:
    history_companies = {
        str(item.get("ticker") or "").upper(): item
        for item in (context["report_history"].get("companies") or [])
        if isinstance(item, dict)
    }
    for decision in context["board"].get("decisions") or []:
        ticker = str(decision.get("ticker") or "").upper()
        path = str(decision.get("report_path") or "")
        entry = history_companies.get(ticker)
        if entry is None:
            audit.add("MEDIUM", "HISTORY_MISSING", company=decision.get("company"), ticker=ticker, report=path, detail="report_history 缺少该公司")
            continue
        paths = {str(item.get("report_path") or "") for item in entry.get("report_history") or []}
        if path and path not in paths:
            audit.add("HIGH", "HISTORY_MISSING_CURRENT", company=decision.get("company"), ticker=ticker, report=path, detail="report_history 不包含当前主报告")


def check_action_guidance(audit: Audit, context: dict[str, Any]) -> None:
    for decision in context["board"].get("decisions") or []:
        company = decision.get("company")
        ticker = decision.get("ticker")
        path = str(decision.get("report_path") or "")
        policy = decision.get("execution_policy") or {}
        guidance = decision.get("action_guidance") or {}
        checklist = decision.get("checklist") or {}
        lifecycle = decision.get("lifecycle")
        primary = decision.get("primary_judgment") or {}
        contract_only = not primary.get("enabled") and bool(decision.get("decision_contract"))
        if policy.get("reliability") == "review" and policy.get("condition_mode") != "review":
            if contract_only:
                audit.add(
                    "LOW",
                    "RELIABILITY_LABEL_CONTRACT",
                    company=company,
                    ticker=ticker,
                    report=path,
                    detail=f"contract-only 决策 reliability 标为 review（contract 置信度驱动 condition_mode={policy.get('condition_mode')}）",
                )
            else:
                audit.add(
                    "HIGH",
                    "GUIDANCE_RELIABILITY_MODE",
                    company=company,
                    ticker=ticker,
                    report=path,
                    detail=f"reliability=review 但 condition_mode={policy.get('condition_mode')}",
                )
        if checklist.get("hard_veto") is True and policy.get("current_action"):
            blocker = str(guidance.get("blocker_code") or "")
            next_action = str(guidance.get("next_action_code") or "")
            gate_enforced = "checklist" in blocker or next_action in {"continue_monitoring", "keep_watch", "none"}
            audit.add(
                "LOW" if gate_enforced else "HIGH",
                "GUIDANCE_CHECKLIST_VETO",
                company=company,
                ticker=ticker,
                report=path,
                detail=(
                    f"hard_veto=true 且 execution_policy 保留 current_action；"
                    f"action_guidance blocker={blocker or '无'} next_action={next_action or '无'}"
                ),
            )
        if lifecycle == "EXITED" and policy.get("current_action"):
            audit.add("HIGH", "GUIDANCE_EXITED_ACTION", company=company, ticker=ticker, report=path, detail="EXITED 仍有 current_action")
        if policy.get("current_action") and not (decision.get("primary_judgment") or {}).get("enabled"):
            audit.add("LOW", "GUIDANCE_CURRENT_WITHOUT_JUDGMENT", company=company, ticker=ticker, report=path, detail="有 current_action 但无 primary_judgment（contract-only 决策）")
        if guidance.get("requires_user_action") and guidance.get("next_action_code") == "continue_monitoring":
            audit.add("LOW", "GUIDANCE_NAVIGATION", company=company, ticker=ticker, report=path, detail="requires_user_action=true 但动作为 continue_monitoring")


def run_audit(root: Path) -> tuple[Audit, dict[str, Any]]:
    context = load_context(root)
    audit = Audit()
    check_selection(audit, context)
    check_identity(audit, context)
    check_cutoff(audit, context)
    check_reference_price(audit, context)
    check_action(audit, context)
    check_stances(audit, context)
    check_price_plan(audit, context)
    check_scenario(audit, context)
    check_checklist(audit, context)
    check_contract(audit, context)
    check_mixed_source(audit, context)
    check_catalog(audit, context)
    check_state_layers(audit, context)
    check_history(audit, context)
    check_action_guidance(audit, context)
    return audit, context


def summary_payload(audit: Audit, context: dict[str, Any]) -> dict[str, Any]:
    board_decisions = context["board"].get("decisions") or []
    fresh = context["fresh_decisions"]
    code_counts: defaultdict[str, int] = defaultdict(int)
    for finding in audit.findings:
        code_counts[finding["code"]] += 1

    def total(*prefixes: str) -> int:
        return sum(
            count
            for code, count in code_counts.items()
            if any(code.startswith(prefix) or code == prefix for prefix in prefixes)
        )

    aggregates = {
        "cutoff_anomalies": total(
            "CUTOFF_",
            "FINANCIAL_PERIOD_CUTOFF",
            "COMPLETED_BEFORE_CUTOFF",
            "CONTRACT_CUTOFF_OVERRIDDEN",
        ),
        "price_anomalies": total(
            "REFERENCE_PRICE_",
            "PRICE_PLAN_",
            "BUY_PRICE_",
            "PRICE_RANGE_",
            "STANCE_CURRENCY",
        ),
        "report_selection_anomalies": total(
            "SELECTION_", "SUBREPORT_SELECTED", "REPORT_PATH_", "TICKER_", "MARKET_", "ENTITY_", "CATALOG_"
        ),
        "mixed_source_records": total("MIXED_SOURCE_"),
        "contract_conflicts": total("CONTRACT_", "ACTION_CONTRACT_MISMATCH"),
        "checklist_conflicts": total("CHECKLIST_"),
        "scenario_anomalies": total("SCENARIO_"),
        "missing_provenance": total(
            "HISTORY_", "STATE_", "CORE_", "BROKEN_REPORT_PATH", "REGISTRY_", "ALIAS_"
        ),
    }
    return {
        "companies": len(board_decisions),
        "current_reports": len(fresh),
        "severity_counts": audit.counts(),
        "aggregates": aggregates,
        "code_counts": dict(sorted(code_counts.items())),
        "findings": audit.findings,
        "reference_prices_parsed": sum(1 for decision in fresh if decision.get("report_reference_price")),
        "scenarios_parsed": sum(1 for decision in fresh if decision.get("scenario_valuation")),
        "checklist_attached": sum(
            1
            for decision in board_decisions
            if (decision.get("checklist") or {}).get("status") not in {None, "missing"}
        ),
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        "report parsing audit",
        f"companies={payload['companies']}",
        f"current reports={payload['current_reports']}",
        "",
        "HIGH={HIGH}  MEDIUM={MEDIUM}  LOW={LOW}".format(**payload["severity_counts"]),
    ]
    for key, value in payload["aggregates"].items():
        lines.append(f"{key.replace('_', ' ')}={value}")
    lines.append("")
    lines.append("code counts:")
    for code, count in payload["code_counts"].items():
        lines.append(f"  {code}={count}")
    lines.append("")
    for severity in SEVERITIES:
        findings = [finding for finding in payload["findings"] if finding["severity"] == severity]
        if not findings:
            continue
        lines.append(f"--- {severity} ({len(findings)}) ---")
        for finding in findings:
            identity = " / ".join(filter(None, (finding.get("company"), finding.get("ticker"))))
            report = f" | {finding['report_path']}" if finding.get("report_path") else ""
            source = f" | source={finding['source']}" if finding.get("source") else ""
            lines.append(f"[{finding['code']}] {identity}{report}{source}")
            if finding.get("detail"):
                lines.append(f"    {finding['detail']}")
            evidence = finding.get("evidence")
            if evidence is not None:
                rendered = json.dumps(evidence, ensure_ascii=False)
                lines.append(f"    evidence={rendered[:400]}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="emit the full audit payload as JSON")
    parser.add_argument("--severity", choices=SEVERITIES, help="print only findings at this severity")
    arguments = parser.parse_args()
    audit, context = run_audit(arguments.repo_root.resolve())
    payload = summary_payload(audit, context)
    if arguments.severity:
        payload["findings"] = [item for item in payload["findings"] if item["severity"] == arguments.severity]
    if arguments.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload))
    return 1 if payload["severity_counts"]["HIGH"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
