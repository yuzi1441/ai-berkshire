#!/usr/bin/env python3
"""Extract conservative Decision Rule candidates from current main reports.

The command is intentionally preview-first.  It reads the canonical reports
already selected by ``build_investment_dashboard.py`` and never edits reports.
Use ``--write`` explicitly to append candidates to the JSON rule layer; low
confidence candidates are stored disabled and marked ``needs_review``.

Examples::

    python3 tools/extract_decision_rules.py --dry-run
    python3 tools/extract_decision_rules.py --write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_investment_dashboard as dashboard  # noqa: E402
from decision_rules import (  # noqa: E402
    ACTION_KEYS,
    SCHEMA_VERSION,
    company_id_for,
    empty_layer,
    normalize_layer,
    normalize_rule,
    stable_rule_id,
)


PRICE_BAND_RE = re.compile(
    r"(?P<currency>HK\$|HKD|RMB|CNY|US\$|USD|\$)?\s*"
    r"(?P<first>\d+(?:\.\d+)?)\s*(?:[—–-]\s*(?P<second>\d+(?:\.\d+)?))?\s*"
    r"(?P<unit>元|港元|美元)?",
    re.IGNORECASE,
)
PRICE_SINGLE_RE = re.compile(
    r"(?P<operator>不高于|不超过|低于|跌破|以下|高于|超过|大于|小于|<=|>=|<|>)\s*"
    r"(?P<currency>HK\$|HKD|RMB|CNY|US\$|USD|\$)?\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>元|港元|美元)?",
    re.IGNORECASE,
)
METRIC_RE = re.compile(
    r"(?P<metric>毛利率|净利率|ROE|收入增速|营收增速|利润增速|订单增速|客户留存率|海外销量|"
    r"经营现金流|自由现金流|现金流|利润率|负债率|储能业务增速)"
    r"[^\n|。；;，,?？]{0,24}?"
    r"(?P<operator>不低于|不超过|低于|跌破|以下|高于|超过|大于|小于|<=|>=|<|>)\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|倍|亿元|万辆|万台)?",
    re.IGNORECASE,
)
EVENT_TERMS = (
    "管理层",
    "接班人",
    "监管",
    "关税",
    "收购",
    "并购",
    "替代",
    "护城河",
    "品牌",
    "商业模式",
    "连续两个季度",
)
TRIGGER_TERMS = ("如果", "若", "一旦", "跌破", "低于", "超过", "不高于", "信号", "红线", "触发", "复核", "失效")
BUY_TERMS = ("买入", "建仓", "配置", "增持", "加仓", "小仓", "分批")
REDUCE_TERMS = ("减仓", "卖出", "退出", "回避", "放弃", "不再持有")
NULL_TEXT = {"", "-", "--", "无", "未给出", "待复核", "不适用"}


def clean(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


def report_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def section_for(lines: list[str], index: int) -> str:
    for cursor in range(index, -1, -1):
        line = lines[cursor].strip()
        if line.startswith("#"):
            return clean(line.lstrip("# "), 160)
    return "主报告正文"


def source_text(lines: list[str], index: int) -> str:
    start = max(0, index - 1)
    end = min(len(lines), index + 2)
    return clean(" ".join(lines[start:end]), 360)


def find_line(lines: list[str], fragment: str, *, prefer_decision: bool = True) -> int:
    fragment = clean(fragment, 120)
    candidates = [index for index, line in enumerate(lines) if fragment and fragment in clean(line, 500)]
    if not candidates:
        return 0
    if prefer_decision:
        ranked = sorted(candidates, key=lambda index: (0 if any(term in lines[index] for term in ("最终", "行动", "建议", "买入", "估值")) else 1, index))
        return ranked[0]
    return candidates[0]


def currency_for(market: str, currency: str | None = None) -> str:
    value = str(currency or "").upper()
    value = {"HK$": "HKD", "US$": "USD", "$": "USD"}.get(value, value)
    if value in {"CNY", "HKD", "USD", "KRW"}:
        return value
    return {"A股": "CNY", "港股": "HKD", "美股": "USD"}.get(market, "")


def parse_band(text: str, market: str) -> tuple[str, Any] | None:
    cleaned = clean(text, 160).replace(",", "")
    if not cleaned or not re.search(r"(?:元|港元|美元|HK\$|HKD|US\$|USD|\$)", cleaned, re.I):
        # A report-selected market may imply the unit, but require a price-like
        # action phrase elsewhere; this parser only handles unambiguous numbers.
        if not re.search(r"\d+(?:\.\d+)?\s*[—–-]\s*\d+(?:\.\d+)?", cleaned):
            return None
    single = PRICE_SINGLE_RE.search(cleaned)
    if single:
        value = number(single.group("value"))
        if value is not None and 0 < value < 1_000_000:
            operator = {
                "不高于": "<=", "不超过": "<=", "低于": "<", "跌破": "<", "以下": "<=",
                "高于": ">", "超过": ">", "大于": ">", "小于": "<",
            }.get(single.group("operator"), single.group("operator"))
            return currency_for(market, single.group("currency")), {"operator": operator, "value": value}
    match = PRICE_BAND_RE.search(cleaned)
    if not match:
        return None
    first = number(match.group("first"))
    second = number(match.group("second"))
    if first is None or first <= 0 or first > 1_000_000:
        return None
    if second is not None:
        if second <= 0 or second > 1_000_000:
            return None
        minimum, maximum = sorted((first, second))
        return currency_for(market, match.group("currency")), {"min": minimum, "max": maximum}
    return currency_for(market, match.group("currency")), {"min": first, "max": first}


def action_for(text: str) -> tuple[str, str, str] | None:
    value = clean(text, 180)
    if any(term in value for term in REDUCE_TERMS):
        return "redline", "review_reduce", "达到减仓/退出复核条件"
    if "加仓" in value:
        return "entry", "review_add", "达到加仓复核条件"
    if any(term in value for term in BUY_TERMS):
        return "entry", "run_checklist", "达到买入前 Checklist 复核条件"
    return None


def make_rule(
    *,
    decision: dict[str, Any],
    report_path: str,
    lines: list[str],
    line_index: int,
    category: str,
    trigger_type: str,
    operator: str = "",
    value: Any = None,
    currency: str = "",
    metric: str = "",
    event_type: str = "",
    action: str = "进入论文复核",
    action_key: str = "thesis_review",
    description: str = "",
    confidence: str = "medium",
    automation: str = "review",
    enabled: bool = True,
    needs_review: bool = False,
    conditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    company = clean(decision.get("company"), 120)
    company_id = company_id_for(decision)
    ticker = clean(decision.get("ticker"), 40).upper()
    market = clean(decision.get("market"), 20)
    source = source_text(lines, line_index)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    rule = {
        "id": stable_rule_id(
            company_id=company_id,
            ticker=ticker,
            market=market,
            trigger_type=trigger_type,
            operator=operator,
            value=value,
            source_report=report_path,
            source_text=source,
        ),
        "company_id": company_id,
        "company": company,
        "ticker": ticker,
        "market": market,
        "category": category,
        "trigger_type": trigger_type,
        "operator": operator,
        "value": value,
        "currency": currency or currency_for(market),
        "metric": metric,
        "event_type": event_type,
        "conditions": conditions or [],
        "action": action,
        "action_key": action_key if action_key in ACTION_KEYS else "thesis_review",
        "description": clean(description or action, 240),
        "source": "main_report",
        "origin": "migration_candidate",
        "source_report": report_path,
        "source_section": section_for(lines, line_index),
        "source_text": source,
        "confidence": confidence,
        "automation": automation,
        "enabled": enabled,
        "needs_review": needs_review,
        "status": "needs_review" if needs_review else "watching",
        "created_at": now,
        "updated_at": now,
    }
    return normalize_rule(rule, now=now)


def explicit_contract_rules(decision: dict[str, Any], report_path: str, lines: list[str]) -> list[dict[str, Any]]:
    """Extract the existing typed contract's invalidation text conservatively."""
    contract = dashboard.extract_decision_contract(lines)
    if not isinstance(contract, dict):
        return []
    invalidation = clean(contract.get("invalidation_triggers"), 800)
    if invalidation in NULL_TEXT:
        return []
    line_index = find_line(lines, invalidation[:80])
    rules: list[dict[str, Any]] = []
    chunks = [clean(item, 280) for item in re.split(r"[；;。]|\s*\d+[)）、]\s*", invalidation) if clean(item)]
    for chunk in chunks[:8]:
        if chunk in NULL_TEXT or len(chunk) < 3:
            continue
        rules.append(
            make_rule(
                decision=decision,
                report_path=report_path,
                lines=lines,
                line_index=line_index,
                category="redline",
                trigger_type="event",
                event_type="论文失效条件",
                action="进入 Thesis Drift / 人工复核",
                action_key="thesis_review",
                description=chunk,
                confidence="medium",
                automation="manual",
                enabled=False,
                needs_review=True,
            )
        )
    return rules


def price_rules(decision: dict[str, Any], report_path: str, lines: list[str], repo_root: Path) -> list[dict[str, Any]]:
    market = clean(decision.get("market"), 20)
    rules: list[dict[str, Any]] = []
    try:
        record = dashboard.candidate_record(
            repo_root / report_path,
            repo_root,
            dashboard.load_registry(repo_root / "data" / "report-routing" / "company_registry.json"),
            dashboard.load_json(repo_root / "data" / "investment-dashboard" / "overrides.json", {"schema_version": 1, "reports": {}, "companies": {}}),
        )
    except (OSError, ValueError):
        record = None
    rows = record.get("price_plan") if isinstance(record, dict) else []
    usable = dashboard.usable_price_plan_rows(rows if isinstance(rows, list) else [], market)
    seen: set[str] = set()
    for row in usable:
        action_info = action_for(str(row.get("action") or row.get("profile") or ""))
        parsed = parse_band(str(row.get("price_range") or ""), market)
        if not action_info or not parsed:
            continue
        currency, value = parsed
        key = f"{value}|{action_info[0]}|{action_info[1]}"
        if key in seen:
            continue
        seen.add(key)
        fragment = str(row.get("price_range") or "")
        line_index = find_line(lines, fragment)
        if "operator" in value:
            trigger_type = "price"
            operator = value["operator"]
            rule_value = value["value"]
        else:
            minimum = value.get("min")
            maximum = value.get("max")
            is_single = minimum == maximum
            trigger_type = "price" if is_single else "price_range"
            operator = "<=" if is_single else ""
            rule_value = minimum if is_single else value
        rules.append(
            make_rule(
                decision=decision,
                report_path=report_path,
                lines=lines,
                line_index=line_index,
                category=action_info[0],
                trigger_type=trigger_type,
                operator=operator,
                value=rule_value,
                currency=currency,
                action=action_info[2],
                action_key=action_info[1],
                description=f"价格达到 {fragment}，{action_info[2]}",
                confidence="high",
                automation="auto",
            )
        )
    return rules


def narrative_metric_rules(decision: dict[str, Any], report_path: str, lines: list[str]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float]] = set()
    for index, line in enumerate(lines):
        cleaned = clean(line, 500)
        if not any(term in cleaned for term in TRIGGER_TERMS):
            continue
        if any(term in cleaned for term in ("交叉验证", "来源差异", "偏差均", "数据偏差")):
            # These are source-quality statements, not investment triggers.
            continue
        for match in METRIC_RE.finditer(cleaned):
            metric = clean(match.group("metric"), 60)
            operator = match.group("operator")
            value = number(match.group("value"))
            if value is None or value <= 0 or value > 1_000_000:
                continue
            if not match.group("unit") and 1900 <= value <= 2100:
                continue
            # Do not turn a year/month/period used as a comparison anchor into
            # a financial threshold (e.g. ``ROE ... lower than 2021``).
            if re.match(r"\s*(?:年|月|日|天|季度|季|Q\d)", cleaned[match.end():], re.I):
                continue
            key = (metric, operator, value)
            if key in seen:
                continue
            seen.add(key)
            action_key = "review_reduce" if any(term in cleaned for term in REDUCE_TERMS) else "thesis_review"
            action = "进入减仓复核" if action_key == "review_reduce" else "进入 Thesis Drift / Review"
            rules.append(
                make_rule(
                    decision=decision,
                    report_path=report_path,
                    lines=lines,
                    line_index=index,
                    category="redline" if action_key == "review_reduce" else "fundamental",
                    trigger_type="metric",
                    operator=operator,
                    value=value,
                    metric=metric,
                    action=action,
                    action_key=action_key,
                    description=f"{metric} {operator} {value}{match.group('unit') or ''}，需要复核",
                    confidence="medium",
                    automation="review",
                    enabled=False,
                    needs_review=True,
                )
            )
    return rules


def narrative_event_rules(decision: dict[str, Any], report_path: str, lines: list[str], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    seen = {str(item.get("source_text") or "") for item in existing}
    for index, line in enumerate(lines):
        cleaned = clean(line, 500)
        if len(cleaned) < 8 or not any(term in cleaned for term in EVENT_TERMS):
            continue
        explicit_signal = any(term in cleaned for term in ("卖出信号", "加仓信号", "减仓信号", "退出信号", "失效条件", "红线", "触发条件", "复核条件"))
        conditional_signal = bool(re.search(r"(?:如果|若|一旦).{0,120}(?:则|将|需要复核|应复核|否则)", cleaned))
        if not explicit_signal and not conditional_signal:
            continue
        if METRIC_RE.search(cleaned):
            # Numeric metric candidates get their own review rule.
            continue
        if any(term in cleaned for term in ("数据截止", "研究日期", "参考价", "目标价")):
            continue
        source = source_text(lines, index)
        if source in seen:
            continue
        seen.add(source)
        is_reduce = any(term in cleaned for term in REDUCE_TERMS) or "红线" in cleaned
        rules.append(
            make_rule(
                decision=decision,
                report_path=report_path,
                lines=lines,
                line_index=index,
                category="redline" if is_reduce else "event",
                trigger_type="event",
                event_type="主报告事件条件",
                action="进入减仓/退出复核" if is_reduce else "进入 Thesis Drift / 人工复核",
                action_key="review_reduce" if is_reduce else "thesis_review",
                description=clean(cleaned, 240),
                confidence="low",
                automation="manual",
                enabled=False,
                needs_review=True,
            )
        )
    return rules


def composite_rules(decision: dict[str, Any], report_path: str, lines: list[str], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create only transparent nested composites from one line with 2 rules."""
    rules_by_line: dict[int, list[dict[str, Any]]] = {}
    for rule in rules:
        index = find_line(lines, str(rule.get("source_text") or "")[:80])
        rules_by_line.setdefault(index, []).append(rule)
    output: list[dict[str, Any]] = []
    for index, children in rules_by_line.items():
        line = clean(lines[index] if 0 <= index < len(lines) else "", 500)
        if len(children) < 2 or not ("且" in line or "并且" in line or "或" in line or "之一" in line):
            continue
        trigger = "all_of" if any(word in line for word in ("且", "并且")) else "any_of"
        output.append(
            make_rule(
                decision=decision,
                report_path=report_path,
                lines=lines,
                line_index=index,
                category="composite",
                trigger_type=trigger,
                action="进入综合 Thesis Review",
                action_key="thesis_review",
                description=line,
                confidence="low",
                automation="manual",
                enabled=False,
                needs_review=True,
                conditions=[{"rule_id": child["id"]} for child in children[:4]],
            )
        )
    return output


def load_targets(repo_root: Path) -> list[dict[str, Any]]:
    board_path = repo_root / "data" / "investment-dashboard" / "decision_board.json"
    payload = dashboard.load_json(board_path, {})
    decisions = payload.get("decisions") if isinstance(payload, dict) else None
    if isinstance(decisions, list) and decisions:
        targets = []
        for decision in decisions:
            if not isinstance(decision, dict) or not decision.get("report_path"):
                continue
            path = repo_root / str(decision["report_path"])
            if path.is_file():
                targets.append(decision)
        if targets:
            return targets
    registry = dashboard.load_registry(repo_root / "data" / "report-routing" / "company_registry.json")
    overrides = dashboard.load_json(repo_root / "data" / "investment-dashboard" / "overrides.json", {"schema_version": 1, "reports": {}, "companies": {}})
    records = []
    for path in sorted((repo_root / "reports").rglob("*.md")):
        try:
            record = dashboard.candidate_record(path, repo_root, registry, overrides)
        except (OSError, ValueError):
            record = None
        if record:
            records.append(record)
    return dashboard.select_decisions(records, overrides)


def scan(repo_root: Path) -> dict[str, Any]:
    targets = load_targets(repo_root)
    all_rules: list[dict[str, Any]] = []
    companies: list[dict[str, Any]] = []
    for decision in targets:
        report_path = str(decision.get("canonical_main_report_path") or decision.get("report_path") or "").replace("\\", "/")
        path = repo_root / report_path
        if not path.is_file():
            companies.append({"company": decision.get("company"), "ticker": decision.get("ticker"), "report_path": report_path, "status": "missing_report", "rules": []})
            continue
        lines = report_lines(path)
        rules = price_rules(decision, report_path, lines, repo_root)
        rules.extend(narrative_metric_rules(decision, report_path, lines))
        rules.extend(explicit_contract_rules(decision, report_path, lines))
        rules.extend(narrative_event_rules(decision, report_path, lines, rules))
        rules.extend(composite_rules(decision, report_path, lines, rules))
        # Stable de-duplication keeps repeated table/narrative references from
        # making the board look more certain than the report is.
        unique: dict[str, dict[str, Any]] = {}
        for rule in rules:
            unique.setdefault(rule["id"], rule)
        rules = list(unique.values())
        all_rules.extend(rules)
        companies.append(
            {
                "company": decision.get("company"),
                "company_id": company_id_for(decision),
                "ticker": decision.get("ticker"),
                "market": decision.get("market"),
                "report_path": report_path,
                "canonical_report_locked": decision.get("canonical_report_locked") is True,
                "rule_count": len(rules),
                "status": "migratable" if rules and not any(rule.get("needs_review") for rule in rules) else "manual_review" if rules else "no_explicit_rules",
                "rules": rules,
            }
        )
    categories = {key: 0 for key in ("price", "fundamental", "event", "composite")}
    for rule in all_rules:
        trigger = rule.get("trigger_type")
        if trigger in {"price", "price_range"}:
            categories["price"] += 1
        elif trigger == "metric":
            categories["fundamental"] += 1
        elif trigger == "event":
            categories["event"] += 1
        elif trigger in {"all_of", "any_of"}:
            categories["composite"] += 1
    manual_companies = [item["company"] for item in companies if item["status"] == "manual_review"]
    no_rule_companies = [item["company"] for item in companies if item["status"] == "no_explicit_rules"]
    migration = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "company_count": len(companies),
        "reports_scanned": sum(1 for item in companies if item["status"] != "missing_report"),
        "successful_rule_count": sum(1 for rule in all_rules if rule.get("enabled") is True and not rule.get("needs_review")),
        "candidate_rule_count": len(all_rules),
        "price_rule_count": categories["price"],
        "fundamental_rule_count": categories["fundamental"],
        "event_rule_count": categories["event"],
        "composite_rule_count": categories["composite"],
        "migratable_company_count": sum(item["status"] == "migratable" for item in companies),
        "manual_review_company_count": len(manual_companies),
        "no_explicit_rule_company_count": len(no_rule_companies),
        "manual_review_companies": manual_companies,
        "no_explicit_rule_companies": no_rule_companies,
    }
    layer = empty_layer()
    layer.update({"generated_at": migration["generated_at"], "migration": migration, "rules": all_rules})
    return {"layer": layer, "migration": migration, "companies": companies}


def merge_layer(existing: Any, candidates: dict[str, Any], *, replace_migration_candidates: bool = False) -> dict[str, Any]:
    current = normalize_layer(existing)
    by_id = {str(rule.get("id")): rule for rule in current.get("rules", [])}
    if replace_migration_candidates:
        by_id = {
            key: rule
            for key, rule in by_id.items()
            if rule.get("origin") not in {"migration_candidate", ""}
        }
    for candidate in candidates["layer"].get("rules", []):
        by_id.setdefault(str(candidate.get("id")), candidate)
    current["rules"] = list(by_id.values())
    current["generated_at"] = candidates["migration"]["generated_at"]
    current["migration"] = candidates["migration"]
    return current


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_preview(result: dict[str, Any], *, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps({"migration": result["migration"], "companies": result["companies"]}, ensure_ascii=False, indent=2))
        return
    migration = result["migration"]
    print(
        "扫描 {company_count} 家当前主报告：候选规则 {candidate_rule_count} 条，成功提取 {successful_rule_count} 条；"
        "价格 {price_rule_count}，基本面 {fundamental_rule_count}，事件 {event_rule_count}，组合 {composite_rule_count}。".format(**migration)
    )
    print(f"可直接迁移 {migration['migratable_company_count']} 家；需人工确认 {migration['manual_review_company_count']} 家；无明确规则 {migration['no_explicit_rule_company_count']} 家。")
    for company in result["companies"]:
        if company["rule_count"] or company["status"] != "migratable":
            print(f"\n{company['company']} ({company.get('ticker') or '无代码'}) · {company['status']} · {company['rule_count']} 条")
            for index, rule in enumerate(company["rules"], 1):
                target = rule.get("value")
                if rule.get("trigger_type") == "metric":
                    target = f"{rule.get('metric')} {rule.get('operator')} {target}"
                elif rule.get("trigger_type") in {"price", "price_range"}:
                    target = f"{rule.get('operator') or 'in'} {target} {rule.get('currency')}"
                print(f"  {index}. {rule['trigger_type'].upper()} · {target} · {rule['description']} · {rule['source_section']}")
    print("\n预览模式：没有写入任何文件。确认候选规则后使用 --write。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只预览候选规则（默认行为）")
    mode.add_argument("--write", action="store_true", help="显式写入 Decision Rules 和迁移统计")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--output", type=Path, help="覆盖 Decision Rules JSON 输出路径")
    parser.add_argument("--replace-migration-candidates", action="store_true", help="写入时用本次扫描替换上一次迁移候选；显式规则仍保留")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    result = scan(repo_root)
    written_to: Path | None = None
    if args.write:
        data_dir = repo_root / "data" / "investment-dashboard"
        output = args.output.resolve() if args.output else data_dir / "decision_rules.json"
        existing = dashboard.load_json(output, empty_layer())
        write_json(output, merge_layer(existing, result, replace_migration_candidates=args.replace_migration_candidates))
        write_json(data_dir / "decision_rule_migration_report.json", {"schema_version": SCHEMA_VERSION, **result["migration"], "companies": result["companies"]})
        write_json(data_dir / "decision_rule_candidates.json", {"schema_version": SCHEMA_VERSION, **result["migration"], "companies": result["companies"]})
        written_to = output
    if args.json:
        output = {"migration": result["migration"], "companies": result["companies"]}
        if written_to:
            output["written_to"] = str(written_to)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_preview(result, json_output=False)
        if written_to:
            print(f"\n已写入：{written_to}")
            print("请随后运行 python3 tools/build_investment_dashboard.py，将规则复制到静态看板并重新生成机会列表。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
