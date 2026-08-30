#!/usr/bin/env python3
"""Versioned, incremental main-report condition review for A-share stocks.

Human resolutions are the only active rule authority.  Independent ZCode rule
packages are retained as audit candidates and never become executable rules
without a manual resolution update.  Evidence review is incremental and writes
one atomic result per stock.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # Snapshot-only dashboard builds do not parse PDFs.
    PdfReader = None

TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in __import__("sys").path:
    __import__("sys").path.insert(0, TOOLS_DIR)

import opportunity_review
import sentiment_snapshot
from source_hash import canonical_file_sha256, canonical_sha256_text


SCHEMA_VERSION = 2
PROTOCOL_VERSION = "main-report-review-v2.3"
PUBLIC_SNAPSHOT_VERSION = 5
DAILY_REVIEW_DUE_DAYS = 3
DEEP_REVIEW_DUE_DAYS = 30
RULE_GROUPS = {"entry", "holder", "improvement", "redline"}
RULE_POLARITIES = {"positive", "negative", "monitoring"}
RULE_STATES = {"active", "stale", "pending_manual_confirmation", "archived"}
SCHEDULE_TYPES = {"price", "filing", "recurring_filing", "event"}
TRUTH_STATES = {"met", "not_met", "unknown", "not_due"}
REVIEW_EFFECTS = {"positive", "neutral", "warning", "redline"}
EVENT_DISCLOSURE_STATES = {
    "not_applicable",
    "disclosed",
    "not_disclosed",
    "not_due",
    "search_incomplete",
}
MISSING_CODES = {
    "no_current_value",
    "no_comparison",
    "no_threshold",
    "no_official_source",
    "no_event_confirmation",
}
MAX_OFFICIAL_EVIDENCE_DOCUMENTS = 12
MAX_OFFICIAL_EVIDENCE_CHARS = 24000
PROTOCOL_FINDING_CATEGORIES = {
    "evidence_gap_pattern",
    "source_access_issue",
    "measurement_mapping_issue",
    "rule_semantic_ambiguity",
    "output_schema_issue",
}
TEXT_EVIDENCE_SUFFIXES = {".md", ".txt"}
OFFICIAL_TITLE_TOKENS = (
    "年度报告",
    "半年度报告",
    "季度报告",
    "业绩说明",
    "投资者关系",
    "调研",
    "订单",
    "中标",
    "项目",
    "产能",
    "回购",
    "监管",
)
FORMAL_FINANCIAL_REPORT_TOKENS = ("年度报告", "半年度报告", "季度报告")
METRIC_PATTERNS: tuple[tuple[str, str], ...] = (
    ("毛利率", r"毛利率|毛利"),
    ("经营现金流", r"经营现金流|经营活动现金流|CFO"),
    ("自由现金流", r"自由现金流|FCF"),
    ("扣非利润", r"扣非利润|扣非净利"),
    ("利润", r"归母净利|归母利润|净利润|利润"),
    ("收入", r"收入|营收|销售额"),
    ("ROE", r"ROE"),
    ("ROIC", r"ROIC"),
    ("订单", r"订单|在手订单|新签订单|中标"),
    ("回款", r"回款|应收账款|应收"),
    ("库存", r"库存|存货"),
    ("债务", r"短债|短期借款|净债务|负债率|杠杆"),
    ("分红", r"分红|股息"),
    ("政策", r"政策|关税|监管"),
    ("产能/销量", r"产能|销量|产量|出货"),
    ("产品/客户", r"产品|客户|服务收入|海外收入|市场份额|认证"),
    ("估值", r"估值|PE|PB|PS|市值"),
)
NEGATIVE_MARKERS = re.compile(
    r"红线|风险|失效|卖出|减仓|清仓|回避|跌破|低于|小于|恶化|下滑|下降|"
    r"不改善|未改善|无法|违约|减值|事故|处罚|造假|爆雷|暂停|推迟|低迷|亏损",
    re.I,
)
# A rule can mention a negative word while still being a *positive* gate, for
# example "经营现金流不继续恶化后才可买入".  Treating every occurrence of
# "恶化" or "下降" as a sell-side red line was the source of false alerts in
# the original coarse `risk` task.  A red line needs an explicit adverse
# outcome; everything else remains a confirmation/monitoring condition.
ADVERSE_OUTCOME_MARKERS = re.compile(
    r"(?:红线|失效|清仓|减仓|卖出|回避|暂停(?:买入|加仓)?|退出|重审|"
    r"维持(?:回避|减仓|卖出)|(?:为|是).*?(?:减仓|回避|卖出)信号)",
    re.I,
)
RISK_MONITORING_MARKERS = re.compile(
    r"(?:核对|跟踪|监测|关注).{0,24}(?:风险|治理|商誉|问询|合规|处罚)",
    re.I,
)
NEGATED_REDLINE_MARKERS = re.compile(
    r"(?:所有|既有|相关)?(?:卖出|风险)?红线(?:均)?未触发",
    re.I,
)
EVENT_MARKERS = re.compile(
    r"公告|订单|中标|客户|认证|政策|监管|投产|量产|项目|回款|整改|获批|落地|事件",
    re.I,
)
FINANCIAL_MARKERS = re.compile(
    r"毛利|现金流|FCF|利润|收入|营收|ROE|ROIC|应收|库存|存货|债务|财报|中报|季报|年报",
    re.I,
)
PRICE_MARKERS = re.compile(r"股价|价格|价位|估值|PE|PB|PS|市值|\d+(?:\.\d+)?\s*元", re.I)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_price_context(repo_root: Path, ticker: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Return the existing quote snapshot as read-only context for a review.

    A quote never becomes fundamental evidence and is deliberately excluded
    from the review input fingerprint: a price change must not cause a model
    rerun.  The dashboard's price partition remains the authority for price
    bands and execution state.
    """
    checked_at = (now or datetime.now().astimezone()).astimezone()
    for path in (
        repo_root / "data" / "investment-dashboard" / "quotes" / "latest.json",
        repo_root / "site" / "data" / "quotes" / "latest.json",
    ):
        payload = load_json(path, {})
        if not isinstance(payload, dict):
            continue
        quote = next(
            (
                row
                for row in (payload.get("quotes") or [])
                if isinstance(row, dict) and str(row.get("ticker") or "") == ticker
            ),
            None,
        )
        if not isinstance(quote, dict):
            continue
        generated_at = str(payload.get("generated_at") or "")
        try:
            age_seconds = max(0, int((checked_at - datetime.fromisoformat(generated_at)).total_seconds()))
        except ValueError:
            age_seconds = None
        freshness = "fresh" if age_seconds is not None and age_seconds <= 600 else "stale"
        return {
            "status": freshness,
            "price": quote.get("price"),
            "currency": quote.get("currency"),
            "change_pct": quote.get("change_pct"),
            "provider_timestamp": quote.get("provider_timestamp"),
            "snapshot_generated_at": generated_at or None,
            "age_seconds": age_seconds,
            "source": quote.get("source") or "quote snapshot",
            "statement": "只读行情上下文；不属于经营复核证据，不得改变规则、真值状态或价格分区。",
        }
    return {
        "status": "missing",
        "price": None,
        "currency": None,
        "change_pct": None,
        "provider_timestamp": None,
        "snapshot_generated_at": None,
        "age_seconds": None,
        "source": None,
        "statement": "未找到行情快照；不得以搜索摘要或推测补充价格。",
    }


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return canonical_sha256_text(encoded)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary_path = Path(temporary.name)
    try:
        with temporary:
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary_path = Path(temporary.name)
    try:
        with temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def metric_names(text: str) -> list[str]:
    return [label for label, pattern in METRIC_PATTERNS if re.search(pattern, text, re.I)]


def period_names(text: str) -> list[str]:
    periods: list[str] = []
    for label, pattern in (
        ("H1", r"中报|半年报|半年度|上半年|H1|Q2|第二季度"),
        ("Q3", r"三季报|第三季度|Q3"),
        ("FY", r"年报|年度报告|年度财报|FY"),
        ("quarterly", r"连续\s*[两二三2-9]?\s*(?:个|期|次)?季度|后续季度|多个季度|每季度|每期财报"),
    ):
        if re.search(pattern, text, re.I):
            periods.append(label)
    return periods


def split_rule_clauses(text: str) -> list[str]:
    """Split only strong sentence boundaries; keep all/any conditions together."""
    cleaned = compact_text(text)
    cleaned = re.sub(r"[（(]\s*[1-9一二三四五六七八九十]+\s*[）)]", "；", cleaned)
    clauses = [compact_text(item) for item in re.split(r"[；。]+", cleaned)]
    return [item for item in clauses if item]


def relation_for(text: str) -> str:
    has_disjunction = bool(re.search(r"任一|任意|之一|或者|或", text))
    has_conjunction = bool(re.search(r"且|同时|并且|并需|并至少|必须|以及", text))
    # A flat all_of/any_of field cannot faithfully encode a nested expression
    # such as "价格满足且基本面确认，或另一项条件".  `any_of` would let one
    # fragment pass the entire rule.  Use all_of for the mixed case until the
    # locked rule is manually split into truly atomic clauses: it fails closed
    # and never fabricates a positive review result.
    if has_disjunction and not has_conjunction:
        return "any_of"
    return "all_of"


def operator_and_threshold(text: str) -> tuple[str | None, str | None]:
    operator = None
    for name, pattern in (
        ("lte", r"不高于|不超过|小于等于|≤|<="),
        ("gte", r"不低于|不少于|大于等于|≥|>="),
        ("lt", r"低于|小于|跌破|<"),
        ("gt", r"高于|大于|超过|>"),
    ):
        if re.search(pattern, text):
            operator = name
            break
    pattern = re.compile(
        r"-?\d+(?:\.\d+)?(?:\s*[-–至]\s*-?\d+(?:\.\d+)?)?\s*(?:%|元|港元|美元|倍|x|亿元|万|GW|GWh|万元)?",
        re.I,
    )
    matches = [compact_text(match.group(0)) for match in pattern.finditer(text)]
    explicit = [
        value
        for value in matches
        if re.search(r"%|元|港元|美元|倍|x|亿元|万|GW|GWh|万元", value, re.I)
    ]
    candidates = explicit or matches
    # One atomic rule may still express an all_of/any_of compound.  When it
    # contains multiple numeric thresholds, keeping a single operator/value
    # would fabricate a pairing that the report never made.
    if len(candidates) != 1:
        return None, None
    return operator, candidates[0]


def evidence_requirements(text: str, schedule_type: str) -> list[str]:
    requirements: list[str] = []
    if schedule_type == "price":
        requirements.append("current_price")
    if FINANCIAL_MARKERS.search(text):
        requirements.append("current_value")
    if re.search(r"同比|环比|连续|改善|恶化|增长|下降|回升|收窄", text):
        requirements.append("comparison")
    if EVENT_MARKERS.search(text):
        requirements.extend(["official_source", "event_confirmation"])
    return list(dict.fromkeys(requirements or ["current_value"]))


def source_lines_from_locked(task: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in task.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "line_start": item.get("line_start"),
                "line_end": item.get("line_end"),
                "quote": compact_text(item.get("quote")),
                "supports": compact_text(item.get("supports")),
            }
        )
    return rows


def locked_group(task: dict[str, Any], clause: str) -> tuple[str, str]:
    task_id = str(task.get("task_id") or "")
    if task_id == "entry":
        return "entry", "positive"
    if task_id == "holder":
        return "holder", "monitoring"
    if NEGATIVE_MARKERS.search(clause):
        return "redline", "negative"
    return "improvement", "positive"


def semantic_group_for_rule(rule: dict[str, Any]) -> str:
    """Return the display/evaluation group without rewriting the locked rule.

    ``group`` is retained verbatim for auditability and stable rule IDs.  Some
    legacy ``risk`` tasks, however, mixed an adverse red line with the positive
    conditions needed before buying or upgrading.  Only a condition with an
    explicit adverse outcome is a red line.  A risk item that merely asks for
    continued monitoring is shown as a holding verification; all other such
    clauses are operating confirmation conditions.
    """
    group = str(rule.get("group") or "")
    if group != "redline":
        return group if group in RULE_GROUPS else "holder"
    condition = compact_text(rule.get("condition"))
    if NEGATED_REDLINE_MARKERS.search(condition):
        return "improvement"
    if ADVERSE_OUTCOME_MARKERS.search(condition):
        return "redline"
    if RISK_MONITORING_MARKERS.search(condition):
        return "holder"
    return "improvement"


def rule_from_clause(
    task: dict[str, Any],
    clause: str,
    index: int,
    *,
    authority: str,
    state: str,
    source_lines: list[dict[str, Any]],
    forced_group: str | None = None,
) -> dict[str, Any]:
    group, polarity = locked_group(task, clause)
    if forced_group:
        group = forced_group
        polarity = "negative" if forced_group == "redline" else polarity
    schedule_type = str(task.get("schedule_type") or "event")
    if schedule_type not in SCHEDULE_TYPES:
        schedule_type = "event"
    if PRICE_MARKERS.search(clause) and not (FINANCIAL_MARKERS.search(clause) or EVENT_MARKERS.search(clause)):
        schedule_type = "price"
    operator, threshold = operator_and_threshold(clause)
    task_id = str(task.get("task_id") or group)
    return {
        "rule_id": f"{authority}.{task_id}.{group}.{index}",
        "group": group,
        "polarity": polarity,
        "state": state,
        "authority": authority,
        "condition": clause,
        "relation": relation_for(clause),
        "metrics": metric_names(clause) or [str(value) for value in task.get("metrics") or []],
        "operator": operator,
        "threshold": threshold,
        "periods": period_names(clause) or [str(value) for value in task.get("periods") or []],
        "schedule_type": schedule_type,
        "evidence_requirement": evidence_requirements(clause, schedule_type),
        "source_field": task.get("source_field"),
        "source_lines": source_lines,
        "reviewable": state == "active" and schedule_type != "price",
    }


def load_resolutions(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "data" / "investment-dashboard" / "main_report_resolutions.json"
    payload = load_json(path, {})
    rows = payload.get("resolutions") or []
    return [
        row
        for row in rows
        if str(row.get("ticker") or "").upper().endswith((".SH", ".SZ", ".BJ"))
        and isinstance(row.get("judgment"), dict)
    ]


def load_zcode_package(repo_root: Path, ticker: str) -> dict[str, Any] | None:
    path = repo_root / "local" / "fundamental-review-zcode" / "full-zcode-rules" / f"{ticker}.json"
    payload = load_json(path, None)
    return payload if isinstance(payload, dict) else None


def build_rule_package(
    repo_root: Path,
    resolution: dict[str, Any],
    zcode: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ticker = str(resolution.get("ticker") or "").upper()
    report_relative = str(resolution.get("report_path") or "")
    report_path = repo_root / report_relative
    if not report_path.is_file():
        raise ValueError(f"main report missing for {ticker}: {report_relative}")
    actual_hash = canonical_file_sha256(report_path)
    expected_hash = str(resolution.get("report_sha256") or "")
    rule_state = "active" if expected_hash == actual_hash else "stale"
    active_rules: list[dict[str, Any]] = []
    for task in (resolution.get("judgment") or {}).get("review_tasks") or []:
        if not isinstance(task, dict):
            continue
        for index, clause in enumerate(split_rule_clauses(str(task.get("content") or "")), start=1):
            active_rules.append(
                rule_from_clause(
                    task,
                    clause,
                    index,
                    authority="human_locked",
                    state="active" if rule_state == "active" else "stale",
                    source_lines=source_lines_from_locked(task),
                )
            )

    audit_candidates: list[dict[str, Any]] = []
    if isinstance(zcode, dict):
        zcode_risk = next(
            (item for item in zcode.get("zcode_tasks") or [] if item.get("task_id") == "risk"),
            None,
        )
        if isinstance(zcode_risk, dict):
            quote = compact_text(zcode_risk.get("derivation_quote"))
            line_ref = zcode_risk.get("derivation_line_ref")
            source_lines = [{"line_start": line_ref, "line_end": line_ref, "quote": quote}]
            for index, clause in enumerate(split_rule_clauses(str(zcode_risk.get("content") or "")), start=1):
                if any(compact_text(rule.get("condition")) == clause for rule in active_rules):
                    continue
                candidate = rule_from_clause(
                    {
                        **zcode_risk,
                        "source_field": "zcode_independent_risk_audit",
                        "schedule_type": zcode_risk.get("schedule_type") or "event",
                    },
                    clause,
                    index,
                    authority="zcode_audit_candidate",
                    state="pending_manual_confirmation",
                    source_lines=source_lines,
                    forced_group="redline",
                )
                candidate["reviewable"] = False
                audit_candidates.append(candidate)

    rules_fingerprint = canonical_json_sha256(
        {
            "protocol_version": PROTOCOL_VERSION,
            "report_sha256": actual_hash,
            "active_rules": active_rules,
        }
    )
    package = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "generated_at": now_iso(),
        "company": resolution.get("company"),
        "ticker": ticker,
        "rule_state": rule_state,
        "authority_policy": {
            "active_authority": "human_locked",
            "model_rule_update": "forbidden",
            "zcode_role": "audit_candidate_only",
        },
        "main_report": {
            "path": report_relative,
            "canonical_sha256": actual_hash,
            "locked_sha256": expected_hash,
            "reviewed_at": resolution.get("reviewed_at"),
        },
        "active_rules": active_rules,
        "audit_candidates": audit_candidates,
        "rules_fingerprint": rules_fingerprint,
        "summary": {
            "active_rule_count": len(active_rules),
            "reviewable_rule_count": sum(rule.get("reviewable") is True for rule in active_rules),
            "price_rule_count": sum(rule.get("schedule_type") == "price" for rule in active_rules),
            "redline_count": sum(semantic_group_for_rule(rule) == "redline" for rule in active_rules),
            "improvement_count": sum(semantic_group_for_rule(rule) == "improvement" for rule in active_rules),
            "pending_redline_candidate_count": len(audit_candidates),
        },
    }
    validate_rule_package(package)
    return package


def validate_rule_package(package: dict[str, Any]) -> None:
    ticker = str(package.get("ticker") or "unknown")
    if package.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"invalid rule schema: {ticker}")
    if package.get("rule_state") not in {"active", "stale"}:
        raise ValueError(f"invalid rule state: {ticker}")
    seen: set[str] = set()
    for rule in [*(package.get("active_rules") or []), *(package.get("audit_candidates") or [])]:
        rule_id = str(rule.get("rule_id") or "")
        if (
            not rule_id
            or rule_id in seen
            or rule.get("group") not in RULE_GROUPS
            or rule.get("polarity") not in RULE_POLARITIES
            or rule.get("state") not in RULE_STATES
            or rule.get("schedule_type") not in SCHEDULE_TYPES
            or rule.get("relation") not in {"all_of", "any_of"}
            or not compact_text(rule.get("condition"))
            or not isinstance(rule.get("metrics"), list)
            or not isinstance(rule.get("periods"), list)
            or not isinstance(rule.get("source_lines"), list)
        ):
            raise ValueError(f"invalid rule in {ticker}: {rule_id or 'missing-id'}")
        seen.add(rule_id)


def migrate_rule_packages(repo_root: Path, rules_dir: Path) -> dict[str, int]:
    rows = load_resolutions(repo_root)
    counts = {"total": len(rows), "active": 0, "stale": 0, "audit_candidates": 0}
    for resolution in rows:
        ticker = str(resolution.get("ticker") or "").upper()
        package = build_rule_package(repo_root, resolution, load_zcode_package(repo_root, ticker))
        atomic_write_json(rules_dir / f"{ticker}.json", package)
        counts[package["rule_state"]] += 1
        counts["audit_candidates"] += len(package["audit_candidates"])
    return counts


def extract_document_date(path: Path, text: str) -> str | None:
    candidates = re.findall(r"20\d{6}", path.name)
    if not candidates:
        header = "\n".join(text.splitlines()[:80])
        labelled = re.search(
            r"(?:复核日期|报告日期|研究日期|建立日期|更新日期|数据截止|财报截止|行情截止|工作日期)"
            r"[^\n]{0,24}?(20\d{2}[-/]\d{1,2}[-/]\d{1,2})",
            header,
        )
        candidates = [labelled.group(1)] if labelled else []
    if not candidates:
        return None
    value = candidates[-1].replace("/", "-")
    if "-" not in value:
        value = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return None


def report_baseline_date(package: dict[str, Any]) -> str | None:
    path = Path(str((package.get("main_report") or {}).get("path") or ""))
    return extract_document_date(path, "") or str((package.get("main_report") or {}).get("reviewed_at") or "")[:10] or None


def is_post_baseline_evidence(document_date: str | None, baseline: str | None) -> bool:
    """Only evidence strictly newer than the locked main report is current."""
    return bool(document_date and baseline and document_date > baseline)


def evidence_candidate_paths(repo_root: Path, package: dict[str, Any]) -> list[Path]:
    report = repo_root / str((package.get("main_report") or {}).get("path") or "")
    if not report.is_file():
        return []
    candidates: list[tuple[str, Path]] = []
    for path in report.parent.rglob("*"):
        name = path.name.lower()
        if not path.is_file() or path == report or path.suffix.lower() not in TEXT_EVIDENCE_SUFFIXES:
            continue
        if any(token in name for token in ("checklist", "technical", "sentiment", "情绪", "技术面")):
            continue
        if not any(token in name for token in ("thesis", "tracker", "source", "复核", "跟踪", "财报")):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        candidates.append((extract_document_date(path, raw) or "0000-00-00", path))
    ordered = [path for _, path in sorted(candidates, key=lambda item: (item[0], item[1].as_posix()), reverse=True)]
    return [report, *ordered[:6]]


def manifest_evidence_rows(repo_root: Path, ticker: str) -> list[dict[str, str]]:
    """Return the already audited local evidence map for the initial migration."""
    manifest = load_json(repo_root / "logs" / "zcode_review_manifest.json", [])
    if not isinstance(manifest, list):
        return []
    entry = next(
        (row for row in manifest if str(row.get("ticker") or "").upper() == ticker),
        None,
    )
    if not isinstance(entry, dict):
        return []
    rows: list[dict[str, str]] = []
    for document in entry.get("docs") or []:
        if not isinstance(document, dict):
            continue
        relative = str(document.get("path") or "")
        role = str(document.get("role") or "")
        if role not in {"main_report_reference", "local_current_evidence"}:
            continue
        if relative and (repo_root / relative).is_file():
            rows.append({"path": relative, "source_role": role})
    return rows


def collect_zcode_evidence_extracts(repo_root: Path, package: dict[str, Any]) -> list[dict[str, Any]]:
    """Reuse current facts already extracted by ZCode without inheriting its verdicts.

    The legacy ZCode packages were produced against an independently extracted,
    coarse three-task rule set.  Their status labels therefore cannot decide a
    human-locked atomic rule.  Exact quotes backed only by audited
    ``local_current_evidence`` documents are still useful current evidence and
    can be passed to the new verifier without being extracted a second time.
    """
    ticker = str(package.get("ticker") or "")
    baseline = report_baseline_date(package)
    zcode = load_zcode_package(repo_root, ticker)
    if not isinstance(zcode, dict) or (zcode.get("model_review") or {}).get("status") != "completed":
        return []

    source_catalog: dict[str, dict[str, Any]] = {}
    for row in zcode.get("local_evidence_documents") or []:
        if not isinstance(row, dict) or row.get("source_role") != "local_current_evidence":
            continue
        relative = str(row.get("path") or "")
        source_path = repo_root / relative
        if not relative or not source_path.is_file():
            continue
        recorded_hash = str(row.get("sha256") or "")
        raw_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        canonical_hash = canonical_file_sha256(source_path)
        raw = source_path.read_text(encoding="utf-8", errors="replace")
        document_date = extract_document_date(source_path, raw)
        if not is_post_baseline_evidence(document_date, baseline):
            continue
        source_catalog[str(row.get("document_id") or "")] = {
            "path": relative,
            "document_date": document_date,
            "canonical_sha256": canonical_hash,
            "recorded_hash_match": not recorded_hash or recorded_hash in {raw_hash, canonical_hash},
            "content": raw,
        }

    extracts: list[dict[str, Any]] = []
    for task in (zcode.get("model_review") or {}).get("tasks") or []:
        if not isinstance(task, dict):
            continue
        evidence_ids = [str(value) for value in task.get("evidence_document_ids") or []]
        evidence_lines = [line for line in task.get("evidence_lines") or [] if isinstance(line, dict)]
        if not evidence_ids or any(value not in source_catalog for value in evidence_ids):
            continue
        if not evidence_lines or any(str(line.get("document_id") or "") not in source_catalog for line in evidence_lines):
            continue
        if any(
            compact_text(line.get("exact_quote"))
            and compact_text(line.get("exact_quote"))
            not in compact_text(source_catalog[str(line.get("document_id") or "")].get("content"))
            for line in evidence_lines
        ):
            continue
        source_dates = [
            str(source_catalog[value].get("document_date") or "")
            for value in evidence_ids
            if source_catalog[value].get("document_date")
        ]
        rendered_lines = [
            "ZCode 已有事实提取（仅复用数据与原文证据，不继承旧状态结论）",
            f"旧任务：{compact_text(task.get('task_id'))}",
            f"已提取数据与比较：{compact_text(task.get('conclusion'))}",
        ]
        provenance = []
        for line in evidence_lines[:8]:
            document_id = str(line.get("document_id") or "")
            source = source_catalog[document_id]
            line_ref = compact_text(line.get("line_ref"))
            quote = compact_text(line.get("exact_quote"))
            rendered_lines.append(f"{source['path']} L{line_ref}: {quote}")
            provenance.append(
                {
                    "path": source["path"],
                    "line_ref": line_ref,
                    "exact_quote": quote,
                    "canonical_sha256": source["canonical_sha256"],
                    "recorded_hash_match": source["recorded_hash_match"],
                }
            )
        extracts.append(
            {
                "document_id": f"zcode_extract_{compact_text(task.get('task_id')) or len(extracts) + 1}",
                "path": f"local/fundamental-review-zcode/full-zcode-rules/{ticker}.json",
                "source_role": "zcode_current_evidence_extract",
                "document_date": max(source_dates, default=None),
                "legacy_task_id": compact_text(task.get("task_id")),
                "fact_summary": compact_text(task.get("conclusion")),
                "canonical_sha256": canonical_json_sha256(
                    {
                        "task_id": task.get("task_id"),
                        "conclusion": task.get("conclusion"),
                        "provenance": provenance,
                    }
                ),
                "content": "\n".join(rendered_lines)[:18000],
                "provenance": provenance,
            }
        )
    return extracts


def collect_local_evidence(repo_root: Path, package: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = report_baseline_date(package)
    task_text = " ".join(
        f"{rule.get('condition', '')} {' '.join(rule.get('metrics') or [])}"
        for rule in package.get("active_rules") or []
    )
    keywords = [
        token
        for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9%./+-]{2,}", task_text)
        if len(token) >= 2
    ]
    ticker = str(package.get("ticker") or "")
    manifest_rows = manifest_evidence_rows(repo_root, ticker)
    manifest_roles = {row["path"]: row["source_role"] for row in manifest_rows}
    manifest_paths = [repo_root / row["path"] for row in manifest_rows]
    discovered_paths = evidence_candidate_paths(repo_root, package)
    paths = list(dict.fromkeys([*manifest_paths, *discovered_paths]))
    documents: list[dict[str, Any]] = []
    for path in paths:
        raw = path.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()
        relative = str(path.relative_to(repo_root))
        is_main = relative == str((package.get("main_report") or {}).get("path") or "")
        document_date = extract_document_date(path, raw)
        if relative in manifest_roles:
            # The historical ZCode manifest predates the versioned-rule
            # protocol, so its `local_current_evidence` label is only a hint.
            # A file from before the locked report must never time-travel into
            # a current verdict.
            manifest_role = manifest_roles[relative]
            if manifest_role == "local_current_evidence":
                role = (
                    "local_current_evidence"
                    if is_post_baseline_evidence(document_date, baseline)
                    else "local_supporting_evidence"
                )
            else:
                role = manifest_role
        elif is_main:
            role = "main_report_reference"
        else:
            role = (
                "local_current_evidence"
                if is_post_baseline_evidence(document_date, baseline)
                else "local_supporting_evidence"
            )
        if role == "main_report_reference":
            selected = [f"L{index + 1}: {line}" for index, line in enumerate(lines)]
        else:
            selected = [
                f"L{index + 1}: {line}"
                for index, line in enumerate(lines)
                if any(keyword in line for keyword in keywords)
            ]
            if not selected:
                selected = [f"L{index + 1}: {line}" for index, line in enumerate(lines[:240])]
        documents.append(
            {
                "document_id": f"local_{len(documents) + 1}",
                "path": relative,
                "source_role": role,
                "document_date": document_date,
                "canonical_sha256": canonical_sha256_text(raw),
                "content": "\n".join(selected)[:18000],
            }
        )
    documents.extend(collect_zcode_evidence_extracts(repo_root, package))
    return documents


def _download_official_pdf(url: str) -> tuple[list[str], str, int]:
    """Download an official PDF without deciding which pages matter yet."""
    if PdfReader is None:
        raise RuntimeError("official PDF review requires the optional pypdf package")
    completed = subprocess.run(
        ["curl", "-fsSL", "--noproxy", "*", "-H", "User-Agent: Mozilla/5.0", url],
        check=True,
        capture_output=True,
        timeout=45,
    )
    with tempfile.TemporaryDirectory(prefix="main-report-review-") as directory:
        path = Path(directory) / "official.pdf"
        path.write_bytes(completed.stdout)
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    return pages, hashlib.sha256(completed.stdout).hexdigest(), len(pages)


def evidence_keywords(package: dict[str, Any]) -> list[str]:
    """Build a compact, rule-led retrieval vocabulary for official filings."""
    values: list[str] = []
    for rule in package.get("active_rules") or []:
        if rule.get("state") != "active" or rule.get("reviewable") is not True:
            continue
        values.extend(str(metric) for metric in (rule.get("metrics") or []) if metric)
        values.extend(re.findall(r"[\u4e00-\u9fffA-Za-z0-9%./+-]{2,16}", str(rule.get("condition") or "")))
    values.extend(("营业收入", "毛利率", "经营现金流", "净利润", "订单", "中标", "回款", "项目", "政策", "监管"))
    return sorted({value for value in values if len(value) >= 2}, key=lambda value: (-len(value), value))


def select_relevant_pdf_evidence(
    pages: list[str],
    package: dict[str, Any],
    *,
    max_chars: int = MAX_OFFICIAL_EVIDENCE_CHARS,
) -> tuple[str, list[int]]:
    """Select rule-relevant PDF passages with page references, not PDF prefixes."""
    keywords = evidence_keywords(package)
    ranked: list[tuple[int, int]] = []
    for page_number, page in enumerate(pages, start=1):
        score = sum(page.count(keyword) * max(2, min(len(keyword), 8)) for keyword in keywords)
        if score:
            ranked.append((score, page_number))
    # A filing's title page is useful only as a fallback.  The normal path is
    # driven by the locked rule vocabulary, so an appendix table can be chosen
    # over the first 18k characters of a long annual report.
    selected_pages: set[int] = set()
    for _, page_number in sorted(ranked, key=lambda row: (-row[0], row[1]))[:12]:
        selected_pages.add(page_number)
        if page_number > 1:
            selected_pages.add(page_number - 1)
        if page_number < len(pages):
            selected_pages.add(page_number + 1)
    if not selected_pages:
        selected_pages.update(range(1, min(len(pages), 3) + 1))

    blocks: list[str] = []
    used_chars = 0
    kept_pages: list[int] = []
    for page_number in sorted(selected_pages):
        page = pages[page_number - 1]
        lines = page.splitlines()
        hit_indexes = [
            index
            for index, line in enumerate(lines)
            if any(keyword in line for keyword in keywords)
        ]
        indexes: set[int] = set()
        for index in hit_indexes:
            indexes.update(range(max(0, index - 3), min(len(lines), index + 4)))
        if not indexes:
            indexes.update(range(min(len(lines), 80)))
        passage = "\n".join(f"P{page_number} L{index + 1}: {lines[index]}" for index in sorted(indexes))
        block = f"[PDF page {page_number}]\n{passage}".strip()
        remaining = max_chars - used_chars
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining]
        blocks.append(block)
        kept_pages.append(page_number)
        used_chars += len(block) + 2
    return "\n\n".join(blocks), kept_pages


def official_candidate_score(row: dict[str, Any], package: dict[str, Any]) -> int:
    title = str(row.get("title") or "")
    score = 0
    if any(token in title for token in FORMAL_FINANCIAL_REPORT_TOKENS) and "摘要" not in title:
        score += 100
    for keyword in evidence_keywords(package):
        if keyword in title:
            score += max(2, min(len(keyword), 10))
    return score


def collect_official_evidence(package: dict[str, Any], *, lookback_days: int = 120) -> list[dict[str, Any]]:
    ticker = str(package.get("ticker") or "")
    company = str(package.get("company") or "")
    baseline = report_baseline_date(package)
    rows = sentiment_snapshot.fetch_cninfo_company_news(
        {"company": company, "ticker": ticker, "market": "A股"},
        display_name=company,
        cutoff=datetime.now().astimezone(),
        lookback_days=lookback_days,
        news_limit=100,
        retrieval_window_type="main_report_incremental_review",
    )
    candidates = [
        row
        for row in rows
        if any(token in str(row.get("title") or "") for token in OFFICIAL_TITLE_TOKENS)
    ]
    # Select according to active-rule coverage rather than a mechanical
    # "first three PDFs" limit.  The safety ceiling controls network/runtime
    # cost, while the page extractor below keeps only rule-relevant passages.
    maximum = min(MAX_OFFICIAL_EVIDENCE_DOCUMENTS, max(4, len([rule for rule in package.get("active_rules") or [] if rule.get("reviewable") is True]) + 2))
    selected = sorted(
        candidates,
        key=lambda row: (-official_candidate_score(row, package), str(row.get("published_at") or "")),
    )[:maximum]
    documents: list[dict[str, Any]] = []
    for row in selected:
        published = str(row.get("published_at") or "")
        if not is_post_baseline_evidence(published[:10] or None, baseline):
            continue
        try:
            pages, sha256, page_count = _download_official_pdf(str(row.get("url") or ""))
        except Exception:
            continue
        content, selected_pages = select_relevant_pdf_evidence(pages, package)
        documents.append(
            {
                "document_id": f"official_{len(documents) + 1}",
                "path": str(row.get("url") or ""),
                "title": row.get("title"),
                "source_role": "official_current_evidence",
                "document_date": published[:10] or None,
                "canonical_sha256": sha256,
                "page_count": page_count,
                "selected_pages": selected_pages,
                "selection_method": "locked_rule_keyword_passages",
                "content": content,
            }
        )
    if not documents:
        documents.append(
            {
                "document_id": "official_search_1",
                "path": "cninfo announcement search",
                "source_role": "official_search_record",
                "document_date": now_iso()[:10],
                "search_coverage": f"巨潮资讯近 {lookback_days} 日，检索标题含规则相关财报/订单/项目/政策/监管关键词",
                "content": "本次官方公告检索未取得主报告基线之后、可供规则核验的正式披露。该记录只能说明本次检索范围，不证明事件未发生。",
            }
        )
    return documents


def evidence_fingerprint(documents: list[dict[str, Any]]) -> str:
    return canonical_json_sha256(
        [
            {
                "path": document.get("path"),
                "source_role": document.get("source_role"),
                "document_date": document.get("document_date"),
                "canonical_sha256": document.get("canonical_sha256"),
            }
            for document in documents
        ]
    )


def input_fingerprint(package: dict[str, Any], documents: list[dict[str, Any]]) -> str:
    return canonical_json_sha256(
        {
            "protocol_version": PROTOCOL_VERSION,
            "rules_fingerprint": package.get("rules_fingerprint"),
            "evidence_fingerprint": evidence_fingerprint(documents),
        }
    )


def effect_for_rule(rule: dict[str, Any], truth_state: str) -> str:
    group = semantic_group_for_rule(rule)
    if truth_state in {"unknown", "not_due"}:
        return "neutral"
    if group == "redline":
        return "redline" if truth_state == "met" else "neutral"
    if group == "improvement":
        return "positive" if truth_state == "met" else "neutral"
    if group == "holder":
        return "warning" if truth_state == "not_met" else "neutral"
    return "positive" if truth_state == "met" else "neutral"


def semantic_relation_for_rule(rule: dict[str, Any]) -> str:
    """Re-evaluate legacy relation metadata from the locked condition text."""
    return relation_for(compact_text(rule.get("condition")))


def review_rules_with_model(
    package: dict[str, Any],
    documents: list[dict[str, Any]],
    price_context: dict[str, Any] | None = None,
    *,
    responder: Any | None = None,
    reviewer_model: str | None = None,
) -> dict[str, Any]:
    active_rules = [
        rule
        for rule in package.get("active_rules") or []
        if rule.get("state") == "active" and rule.get("reviewable") is True
    ]
    task_catalog = {
        rule["rule_id"]: {
            key: rule.get(key)
            for key in (
                "group",
                "polarity",
                "condition",
                "metrics",
                "operator",
                "threshold",
                "periods",
                "schedule_type",
                "evidence_requirement",
            )
        }
        for rule in active_rules
    }
    for rule_id, task in task_catalog.items():
        task["relation"] = semantic_relation_for_rule(
            next(rule for rule in active_rules if rule["rule_id"] == rule_id)
        )
    document_catalog = {
        document["document_id"]: {
            "path": document.get("path"),
            "source_role": document.get("source_role"),
            "document_date": document.get("document_date"),
            "content": document.get("content"),
        }
        for document in documents
    }
    config = opportunity_review.model_config("scan_flash") if responder is None else None
    system = (
        "你是主报告锁定规则的证据核验员。规则由人工锁定，你无权新增、删除、修改、放宽、"
        "重解释任何条件或阈值。main_report_reference 只能证明规则来源，不能证明当前状态。"
        "只有 local_current_evidence、zcode_current_evidence_extract 或 official_current_evidence 可用于 met/not_met；"
        "zcode_current_evidence_extract 只复用旧任务抽取的当前值与原文证据，旧任务的状态结论无效；"
        "local_supporting_evidence 也不能单独证明当前状态。缺少当前值、对比期或事件确认必须 unknown。"
        "price_context 只是看板行情快照，绝不是经营证据；不得用它判断任何规则真值、修改价格带或触发投资动作。"
        "事件规则：只有正式官方披露及原文定位才能写 disclosed 并判 met/not_met；已检索但未披露必须写 not_disclosed + unknown，"
        "不能把未披露当作未发生。not_due 仅适用于规则明确给出且尚未到达的未来事件窗口。"
        "只返回事实核验，不给投资、仓位或交易建议。严格输出 JSON。"
    )
    user = json.dumps(
        {
            "schema": {
                "rule_results": [
                    {
                        "rule_id": "必须与 task_catalog 一一对应",
                        "truth_state": "only met/not_met/unknown/not_due",
                        "current_value": "当前值或空字符串",
                        "comparison": "与阈值/对比期的简短比较或空字符串",
                        "disclosure_state": "event only: disclosed/not_disclosed/not_due/search_incomplete; otherwise not_applicable",
                        "evidence_document_ids": "最多3个 document_catalog id",
                        "evidence_lines": "最多3项：document_id,line_ref,exact_quote",
                        "missing_codes": "only no_current_value/no_comparison/no_threshold/no_official_source/no_event_confirmation",
                    }
                ],
                "rule_update": "must be manual_only",
                "protocol_findings": [
                    {
                        "category": "only evidence_gap_pattern/source_access_issue/measurement_mapping_issue/rule_semantic_ambiguity/output_schema_issue",
                        "observation": "仅记录本次已观察到的流程问题，不提出规则、阈值或投资动作修改",
                        "rule_ids": "仅 task_catalog 内的 id，最多3个",
                        "evidence_document_ids": "仅 document_catalog 内的 id，最多3个",
                        "review_question": "交给后续规范汇总人工审阅的问题，最多180字",
                    }
                ],
            },
            "task_catalog": task_catalog,
            "document_catalog": document_catalog,
            "price_context": price_context or {"status": "missing", "statement": "没有可用行情快照"},
            "verification_policy": {
                "main_report_reference": "baseline_only",
                "local_supporting_evidence": "context_only",
                "current_verdict_roles": [
                    "local_current_evidence",
                    "zcode_current_evidence_extract",
                    "official_current_evidence",
                ],
            },
        },
        ensure_ascii=False,
    )
    if responder is None:
        response, reasoning = opportunity_review.request_json(config, system=system, user=user)
        selected_model = config.model
    else:
        response, reasoning = responder(system, user)
        selected_model = reviewer_model or "external-reviewer"
    if not isinstance(response, dict):
        raise RuntimeError("review responder did not return a JSON object")
    raw_results = (
        response.get("rule_results")
        or response.get("task_results")
        or response.get("results")
        or response.get("rules")
        or response.get("tasks")
    )
    if not isinstance(raw_results, list):
        for container_key in ("data", "review", "output"):
            container = response.get(container_key)
            if not isinstance(container, dict):
                continue
            raw_results = (
                container.get("rule_results")
                or container.get("task_results")
                or container.get("results")
                or container.get("rules")
                or container.get("tasks")
            )
            if isinstance(raw_results, list):
                break
    if not isinstance(raw_results, list):
        raise RuntimeError("model did not return rule_results")
    by_id: dict[str, dict[str, Any]] = {}
    allowed_current_roles = {
        "local_current_evidence",
        "zcode_current_evidence_extract",
        "official_current_evidence",
    }
    for raw in raw_results:
        if not isinstance(raw, dict):
            continue
        rule_id = str(raw.get("rule_id") or "")
        if rule_id not in task_catalog or rule_id in by_id:
            raise RuntimeError(f"unknown or duplicate rule_id: {rule_id!r}")
        truth_state = str(raw.get("truth_state") or "")
        if truth_state not in TRUTH_STATES:
            raise RuntimeError(f"invalid truth_state: {truth_state!r}")
        evidence_ids = [str(value) for value in (raw.get("evidence_document_ids") or [])[:3]]
        if any(value not in document_catalog for value in evidence_ids):
            raise RuntimeError(f"unknown evidence id for {rule_id}")
        missing_codes = [str(value) for value in (raw.get("missing_codes") or [])[:5]]
        if any(value not in MISSING_CODES for value in missing_codes):
            raise RuntimeError(f"invalid missing code for {rule_id}")
        evidence_lines = []
        for line in (raw.get("evidence_lines") or [])[:3]:
            if not isinstance(line, dict) or str(line.get("document_id") or "") not in evidence_ids:
                raise RuntimeError(f"invalid evidence line for {rule_id}")
            evidence_lines.append(
                {
                    "document_id": str(line.get("document_id") or ""),
                    "line_ref": str(line.get("line_ref") or ""),
                    "exact_quote": str(line.get("exact_quote") or ""),
                }
            )
        current_ids = [
            value
            for value in evidence_ids
            if document_catalog[value].get("source_role") in allowed_current_roles
        ]
        rule = next(rule for rule in active_rules if rule["rule_id"] == rule_id)
        schedule_type = str(rule.get("schedule_type") or "event")
        disclosure_state = str(raw.get("disclosure_state") or "not_applicable")
        if disclosure_state not in EVENT_DISCLOSURE_STATES:
            disclosure_state = "search_incomplete" if schedule_type == "event" else "not_applicable"
        if schedule_type != "event":
            disclosure_state = "not_applicable"
        elif truth_state == "not_due":
            # Existing locked rules do not carry an explicit future event date.
            # Do not allow the model to hide an unverified event behind not_due.
            truth_state = "unknown"
            disclosure_state = "search_incomplete"
            if "no_event_confirmation" not in missing_codes:
                missing_codes.append("no_event_confirmation")
        elif disclosure_state == "not_disclosed":
            truth_state = "unknown"
            if "no_event_confirmation" not in missing_codes:
                missing_codes.append("no_event_confirmation")
        if truth_state in {"met", "not_met"} and (not current_ids or not evidence_lines):
            truth_state = "unknown"
            evidence_ids = current_ids
            evidence_lines = [line for line in evidence_lines if line["document_id"] in current_ids]
            if "no_current_value" not in missing_codes:
                missing_codes.append("no_current_value")
        requirements = set(task_catalog[rule_id].get("evidence_requirement") or [])
        inferred_missing: list[str] = []
        if "current_value" in requirements and not compact_text(raw.get("current_value")):
            inferred_missing.append("no_current_value")
        if "comparison" in requirements and not compact_text(raw.get("comparison")):
            inferred_missing.append("no_comparison")
        has_official_current = any(
            document_catalog[value].get("source_role") == "official_current_evidence"
            for value in current_ids
        )
        has_search_record = any(
            document.get("source_role") == "official_search_record"
            for document in document_catalog.values()
        )
        if "official_source" in requirements and not has_official_current and not (
            schedule_type == "event" and disclosure_state == "not_disclosed" and has_search_record
        ):
            inferred_missing.append("no_official_source")
        if "event_confirmation" in requirements and (
            disclosure_state != "disclosed" or not has_official_current or not evidence_lines
        ):
            inferred_missing.append("no_event_confirmation")
        for code in inferred_missing:
            if code not in missing_codes:
                missing_codes.append(code)
        # A compound rule is inconclusive when any required component is absent.
        # This intentionally fails closed for both met and not_met.
        if truth_state in {"met", "not_met"} and missing_codes:
            truth_state = "unknown"
        by_id[rule_id] = {
            "rule_id": rule_id,
            "truth_state": truth_state,
            "review_effect": effect_for_rule(rule, truth_state),
            "current_value": compact_text(raw.get("current_value")),
            "comparison": compact_text(raw.get("comparison")),
            "disclosure_state": disclosure_state,
            "evidence_document_ids": evidence_ids,
            "evidence_lines": evidence_lines,
            "missing_codes": missing_codes,
        }
    results = []
    for rule in active_rules:
        results.append(
            by_id.get(
                rule["rule_id"],
                {
                    "rule_id": rule["rule_id"],
                    "truth_state": "unknown",
                    "review_effect": "neutral",
                    "current_value": "",
                    "comparison": "",
                    "disclosure_state": "search_incomplete" if rule.get("schedule_type") == "event" else "not_applicable",
                    "evidence_document_ids": [],
                    "evidence_lines": [],
                    "missing_codes": ["no_current_value"],
                },
            )
        )
    protocol_findings = []
    for raw in (response.get("protocol_findings") or [])[:3]:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or "")
        observation = compact_text(raw.get("observation"))[:280]
        question = compact_text(raw.get("review_question"))[:180]
        rule_ids = [str(value) for value in (raw.get("rule_ids") or [])[:3]]
        evidence_ids = [str(value) for value in (raw.get("evidence_document_ids") or [])[:3]]
        if (
            category not in PROTOCOL_FINDING_CATEGORIES
            or not observation
            or not question
            or any(value not in task_catalog for value in rule_ids)
            or any(value not in document_catalog for value in evidence_ids)
        ):
            continue
        protocol_findings.append(
            {
                "category": category,
                "observation": observation,
                "rule_ids": rule_ids,
                "evidence_document_ids": evidence_ids,
                "review_question": question,
            }
        )
    return {
        "status": "completed",
        "rule_update": "manual_only",
        "model": selected_model,
        "reasoning": reasoning,
        "rules": results,
        "protocol_findings": protocol_findings,
    }


def aggregate_review_status(package: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {rule["rule_id"]: rule for rule in package.get("active_rules") or []}
    redlines = [row for row in results if row.get("review_effect") == "redline"]
    warnings = [row for row in results if row.get("review_effect") == "warning"]
    positives = [row for row in results if row.get("review_effect") == "positive"]
    unknown = [row for row in results if row.get("truth_state") == "unknown"]
    if redlines:
        status = "redline"
        label = "红线已触发"
    elif warnings:
        status = "attention"
        label = "需要关注"
    elif unknown:
        status = "data_gap"
        label = "存在数据缺口"
    elif positives:
        status = "improving"
        label = "改善条件命中"
    else:
        status = "clear"
        label = "暂无确认红线"
    return {
        "status": status,
        "label": label,
        "redline_count": len(redlines),
        "warning_count": len(warnings),
        "positive_count": len(positives),
        "unknown_count": len(unknown),
        "redline_rule_ids": [row["rule_id"] for row in redlines],
        "missing_requirements": sorted(
            {
                requirement
                for row in unknown
                for requirement in (by_id.get(row["rule_id"], {}).get("evidence_requirement") or [])
            }
        ),
    }


def result_payload(
    package: dict[str, Any],
    documents: list[dict[str, Any]],
    model_review: dict[str, Any] | None,
    *,
    status: str | None = None,
    message: str | None = None,
    price_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fingerprint = input_fingerprint(package, documents)
    current_documents = [
        document
        for document in documents
        if document.get("source_role") in {
            "local_current_evidence",
            "official_current_evidence",
            "zcode_current_evidence_extract",
        }
    ]
    results = (model_review or {}).get("rules") or []
    if status is None:
        summary = aggregate_review_status(package, results)
    else:
        summary = {
            "status": status,
            "label": {
                "stale_rules": "主报告已变化",
                "waiting_evidence": "等待新证据",
                "no_rules": "暂无可复核规则",
                "error": "复核失败",
            }.get(status, status),
            "redline_count": 0,
            "warning_count": 0,
            "positive_count": 0,
            "unknown_count": sum(rule.get("reviewable") is True for rule in package.get("active_rules") or []),
            "redline_rule_ids": [],
            "missing_requirements": sorted(
                {
                    requirement
                    for rule in package.get("active_rules") or []
                    if rule.get("reviewable") is True
                    for requirement in rule.get("evidence_requirement") or []
                }
            ),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "generated_at": now_iso(),
        "company": package.get("company"),
        "ticker": package.get("ticker"),
        "input_fingerprint": fingerprint,
        "rules_fingerprint": package.get("rules_fingerprint"),
        "evidence_fingerprint": evidence_fingerprint(documents),
        "rule_state": package.get("rule_state"),
        "message": message,
        "main_report": package.get("main_report"),
        "price_context": price_context or {"status": "missing", "statement": "本次未读取行情快照。"},
        "evidence_documents": [
            {key: value for key, value in document.items() if key != "content"}
            for document in documents
        ],
        "current_evidence_count": len(current_documents),
        "latest_evidence_date": max(
            (str(document.get("document_date") or "") for document in current_documents),
            default=None,
        ) or None,
        "model_review": model_review,
        "protocol_findings": (model_review or {}).get("protocol_findings") or [],
        "summary": summary,
    }


def load_rule_packages(rules_dir: Path) -> list[dict[str, Any]]:
    packages = []
    for path in sorted(rules_dir.glob("*.json")):
        package = load_json(path, {})
        validate_rule_package(package)
        packages.append(package)
    return packages


def process_package(
    repo_root: Path,
    package: dict[str, Any],
    output_dir: Path,
    *,
    include_official: bool,
    dry_run: bool,
) -> tuple[str, str, dict[str, Any] | None]:
    ticker = str(package.get("ticker") or "")
    price_context = read_price_context(repo_root, ticker)
    documents = collect_local_evidence(repo_root, package)
    if include_official and not any(
        document.get("source_role") in {"local_current_evidence", "zcode_current_evidence_extract"}
        for document in documents
    ):
        documents.extend(collect_official_evidence(package))
    fingerprint = input_fingerprint(package, documents)
    output_path = output_dir / f"{ticker}.json"
    existing = load_json(output_path, {})
    if existing.get("input_fingerprint") == fingerprint and existing.get("summary", {}).get("status") != "error":
        return ticker, "skipped", existing
    if package.get("rule_state") != "active":
        payload = result_payload(package, documents, None, status="stale_rules", message="主报告内容已变化，旧规则只读留档，等待人工重建", price_context=price_context)
        if not dry_run:
            atomic_write_json(output_path, payload)
        return ticker, "stale", payload
    reviewable = [rule for rule in package.get("active_rules") or [] if rule.get("reviewable") is True]
    if not reviewable:
        payload = result_payload(package, documents, None, status="no_rules", message="当前只有价格规则，由人工复核价格分区处理", price_context=price_context)
        if not dry_run:
            atomic_write_json(output_path, payload)
        return ticker, "no_rules", payload
    current_documents = [
        document
        for document in documents
        if document.get("source_role")
        in {"local_current_evidence", "zcode_current_evidence_extract", "official_current_evidence"}
    ]
    if not current_documents:
        payload = result_payload(package, documents, None, status="waiting_evidence", message="没有主报告基线之后的新证据，本次不调用模型", price_context=price_context)
        if not dry_run:
            atomic_write_json(output_path, payload)
        return ticker, "waiting", payload
    if dry_run:
        return ticker, "due", None
    try:
        model_review = review_rules_with_model(package, documents, price_context=price_context)
        payload = result_payload(package, documents, model_review, price_context=price_context)
    except Exception as exc:
        payload = result_payload(package, documents, None, status="error", message=str(exc), price_context=price_context)
        atomic_write_json(output_path, payload)
        return ticker, "error", payload
    atomic_write_json(output_path, payload)
    return ticker, "completed", payload


def run_incremental(
    repo_root: Path,
    rules_dir: Path,
    output_dir: Path,
    *,
    tickers: set[str] | None = None,
    include_official: bool = False,
    dry_run: bool = False,
    workers: int = 4,
) -> dict[str, Any]:
    packages = [
        package
        for package in load_rule_packages(rules_dir)
        if not tickers or str(package.get("ticker") or "") in tickers
    ]
    counts = {key: 0 for key in ("total", "completed", "waiting", "stale", "no_rules", "skipped", "due", "error")}
    counts["total"] = len(packages)
    errors: list[dict[str, str]] = []

    def one(package: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
        return process_package(
            repo_root,
            package,
            output_dir,
            include_official=include_official,
            dry_run=dry_run,
        )

    worker_count = max(1, min(workers, len(packages) or 1))
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="main-report-review") as pool:
        future_map = {pool.submit(one, package): package for package in packages}
        for future in as_completed(future_map):
            package = future_map[future]
            try:
                ticker, status, _ = future.result()
                counts[status] += 1
                print(f"{ticker}: {status}", flush=True)
            except Exception as exc:
                ticker = str(package.get("ticker") or "")
                counts["error"] += 1
                errors.append({"ticker": ticker, "error": str(exc)})
                if not dry_run:
                    error_payload = result_payload(package, [], None, status="error", message=str(exc))
                    atomic_write_json(output_dir / f"{ticker}.json", error_payload)
                print(f"{ticker}: error: {exc}", flush=True)
    return {"generated_at": now_iso(), "counts": counts, "errors": errors}


def protocol_findings_snapshot(output_dir: Path) -> dict[str, Any]:
    """Aggregate observed process issues without changing the active protocol."""
    findings: list[dict[str, Any]] = []
    inputs: list[dict[str, str]] = []
    for path in sorted(output_dir.glob("*.json")):
        payload = load_json(path, {})
        if not isinstance(payload, dict) or not payload.get("ticker"):
            continue
        inputs.append({"path": path.name, "sha256": canonical_file_sha256(path)})
        ticker = str(payload.get("ticker"))
        summary = payload.get("summary") or {}
        rule_state = str(payload.get("rule_state") or (payload.get("main_report") or {}).get("rule_state") or "")
        if rule_state == "stale" or summary.get("status") in {"stale_rules", "rule_stale"}:
            findings.append({"category": "rule_version_stale", "ticker": ticker, "observation": "主报告版本已变化，旧规则已停止参与当前复核。", "review_question": "新版主报告锁定流程是否完整保留了哈希、行号和旧规则只读历史？"})
        if summary.get("status") in {"waiting_evidence", "data_insufficient", "waiting_official_disclosure"}:
            findings.append({"category": "evidence_gap_pattern", "ticker": ticker, "observation": "本轮没有主报告基线之后的当前证据，模型未运行。", "review_question": "该类公司应补充哪一种正式披露或本地跟踪资料，才能在下次复核？"})
        for finding in payload.get("protocol_findings") or []:
            if not isinstance(finding, dict):
                continue
            category = str(finding.get("category") or "")
            if category not in PROTOCOL_FINDING_CATEGORIES:
                continue
            findings.append({"category": category, "ticker": ticker, **finding})
    by_category: dict[str, dict[str, Any]] = {}
    for finding in findings:
        category = str(finding["category"])
        row = by_category.setdefault(category, {"category": category, "count": 0, "tickers": [], "examples": []})
        row["count"] += 1
        if finding["ticker"] not in row["tickers"]:
            row["tickers"].append(finding["ticker"])
        if len(row["examples"]) < 5:
            row["examples"].append({key: finding.get(key) for key in ("ticker", "observation", "review_question", "rule_ids", "evidence_document_ids") if finding.get(key) not in (None, [], "")})
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": "candidate_review_only",
        "policy": "本文件只汇总规范改进候选；不会自动修改主报告规则、红线、阈值、价格分区或执行中的规范。",
        "input_fingerprint": canonical_json_sha256(inputs),
        "input_files": inputs,
        "finding_count": len(findings),
        "categories": sorted(by_category.values(), key=lambda row: (-row["count"], row["category"])),
    }


def codex_direct_manual_snapshot(source_dir: Path) -> dict[str, Any]:
    """Publish a compact, explicitly labelled archive of Codex direct reviews.

    This is a human/Codex evidence layer.  It is deliberately not converted to
    a DeepSeek result and never replaces the manually locked report rules.
    """
    reviews = []
    inputs = []
    status_counts: dict[str, int] = {}
    for path in sorted(source_dir.glob("*.json")):
        if path.name == "protocol-findings-current.json":
            continue
        payload = load_json(path, {})
        reviewer = payload.get("reviewer") if isinstance(payload, dict) else {}
        if not isinstance(reviewer, dict) or reviewer.get("type") != "codex_direct_manual":
            continue
        ticker = str(payload.get("ticker") or "")
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if not ticker or not summary:
            continue
        evidence = [row for row in (payload.get("evidence") or []) if isinstance(row, dict)]
        dated_evidence = sorted(
            (str(row.get("published_at") or row.get("document_date") or "") for row in evidence if row.get("published_at") or row.get("document_date")),
            reverse=True,
        )
        status = str(summary.get("status") or "data_insufficient")
        status_counts[status] = status_counts.get(status, 0) + 1
        inputs.append({"path": path.name, "sha256": canonical_file_sha256(path)})
        reviews.append(
            {
                "ticker": ticker,
                "company": payload.get("company"),
                "reviewed_at": payload.get("reviewed_at"),
                "reviewer": "Codex 直接复核（未调用模型）",
                "rule_state": (payload.get("main_report") or {}).get("rule_state"),
                "status": status,
                "label": summary.get("label") or status,
                "redline_count": len(summary.get("redline_rule_ids") or []),
                "warning_count": len(summary.get("warning_rule_ids") or []),
                "positive_count": len(summary.get("positive_rule_ids") or []),
                "data_gaps": summary.get("data_gaps") or [],
                "next_evidence": summary.get("next_evidence"),
                "evidence_count": len(evidence),
                "latest_evidence_date": dated_evidence[0] if dated_evidence else None,
                "source_statement": reviewer.get("statement"),
                "decision_boundary": summary.get("decision_boundary"),
            }
        )
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source": "Codex direct manual reviews; not a DeepSeek model result and not a replacement for human-locked rules.",
        "input_fingerprint": canonical_json_sha256(inputs),
        "input_files": inputs,
        "stock_count": len(reviews),
        "status_counts": status_counts,
        "reviews": reviews,
    }


def comparison_snapshot(repo_root: Path) -> dict[str, Any]:
    manifest = load_json(repo_root / "logs" / "zcode_review_manifest.json", [])
    locked_dir = repo_root / "local" / "fundamental-review-full"
    zcode_dir = repo_root / "local" / "fundamental-review-zcode" / "full-zcode-rules"
    pairs: dict[str, int] = {}
    task_same = {task_id: 0 for task_id in ("entry", "holder", "risk")}
    divergent: list[dict[str, Any]] = []
    inputs = []
    all_same_stocks = 0
    for entry in manifest:
        ticker = str(entry.get("ticker") or "")
        locked_path = locked_dir / f"{ticker}.json"
        zcode_path = zcode_dir / f"{ticker}.json"
        locked = load_json(locked_path, {})
        zcode = load_json(zcode_path, {})
        inputs.extend(
            [
                {"path": str(locked_path.relative_to(repo_root)), "sha256": canonical_file_sha256(locked_path)},
                {"path": str(zcode_path.relative_to(repo_root)), "sha256": canonical_file_sha256(zcode_path)},
            ]
        )
        locked_tasks = {row.get("task_id"): row for row in (locked.get("model_review") or {}).get("tasks") or []}
        zcode_tasks = {row.get("task_id"): row for row in (zcode.get("model_review") or {}).get("tasks") or []}
        stock_same = True
        for task_id in ("entry", "holder", "risk"):
            left = str((locked_tasks.get(task_id) or {}).get("status") or "missing")
            right = str((zcode_tasks.get(task_id) or {}).get("status") or "missing")
            key = f"{left}|{right}"
            pairs[key] = pairs.get(key, 0) + 1
            if left == right:
                task_same[task_id] += 1
            else:
                stock_same = False
                divergent.append(
                    {
                        "ticker": ticker,
                        "company": entry.get("company"),
                        "task_id": task_id,
                        "locked_status": left,
                        "zcode_status": right,
                        "trigger_related": "triggered" in {left, right},
                    }
                )
        if stock_same:
            all_same_stocks += 1
    total = sum(pairs.values())
    same = sum(count for key, count in pairs.items() if key.split("|")[0] == key.split("|")[1])
    return {
        "schema_version": 2,
        "generated_at": now_iso(),
        "input_fingerprint": canonical_json_sha256(inputs),
        "input_files": inputs,
        "summary": {
            "total_tasks": total,
            "same_tasks": same,
            "divergent_tasks": total - same,
            "all_same_stocks": all_same_stocks,
            "divergent_stocks": len({row["ticker"] for row in divergent}),
            "trigger_related_differences": sum(row["trigger_related"] for row in divergent),
            "trigger_related_stocks": len({row["ticker"] for row in divergent if row["trigger_related"]}),
            "task_same": task_same,
        },
        "pairs": pairs,
        "divergent": divergent,
        "stale_policy": "This snapshot is current only while input_fingerprint matches all listed input files.",
    }


def comparison_snapshot_is_current(repo_root: Path, snapshot: dict[str, Any]) -> bool:
    files = snapshot.get("input_files") if isinstance(snapshot, dict) else None
    if not isinstance(files, list) or not files:
        return False
    expected = canonical_json_sha256(files)
    if snapshot.get("input_fingerprint") != expected:
        return False
    for row in files:
        if not isinstance(row, dict):
            return False
        path = repo_root / str(row.get("path") or "")
        if not path.is_file() or canonical_file_sha256(path) != row.get("sha256"):
            return False
    return True


def render_comparison_markdown(snapshot: dict[str, Any]) -> str:
    summary = snapshot["summary"]
    lines = [
        "# 当前规则与复核结果对照",
        "",
        f"- 生成时间：{snapshot['generated_at']}",
        f"- 输入指纹：`{snapshot['input_fingerprint']}`",
        f"- 一致任务：{summary['same_tasks']}/{summary['total_tasks']}",
        f"- 分歧任务：{summary['divergent_tasks']}",
        f"- 全任务一致股票：{summary['all_same_stocks']}/93",
        f"- triggered 相关分歧：{summary['trigger_related_differences']} 条，涉及 {summary['trigger_related_stocks']} 只",
        "",
        "> 本报告只对当前列出的输入文件有效；任何单股结果更新后必须重新生成。",
        "",
        "## Triggered 相关分歧",
        "",
        "| 股票 | 任务 | 人工锁定轮 | ZCode审计轮 |",
        "|---|---|---|---|",
    ]
    for row in snapshot.get("divergent") or []:
        if not row.get("trigger_related"):
            continue
        lines.append(
            f"| {row.get('company')} ({row.get('ticker')}) | {row.get('task_id')} | "
            f"{row.get('locked_status')} | {row.get('zcode_status')} |"
        )
    return "\n".join(lines) + "\n"


def compact_legacy_daily_review(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Expose the saved DeepSeek daily run without promoting it to a rule verdict."""
    model_review = payload.get("model_review") if isinstance(payload, dict) else None
    if not isinstance(model_review, dict) or model_review.get("status") != "completed":
        return None
    tasks = []
    for task in model_review.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        evidence_lines = []
        for line in task.get("evidence_lines") or []:
            if not isinstance(line, dict):
                continue
            evidence_lines.append(
                {
                    "document_id": line.get("document_id"),
                    "line_ref": line.get("line_ref"),
                    "exact_quote": line.get("exact_quote"),
                }
            )
        tasks.append(
            {
                "task_id": task.get("task_id"),
                "status": task.get("status") or "unknown",
                "evidence_count": len(task.get("evidence_document_ids") or []),
                "missing_codes": task.get("missing_codes") or [],
                "evidence_lines": evidence_lines[:3],
            }
        )
    return {
        "model": model_review.get("model") or "deepseek-v4-flash",
        "generated_at": payload.get("generated_at"),
        "scope": payload.get("scope") or "历史全量日常复核",
        "tasks": tasks,
        "local_evidence_count": len(payload.get("local_evidence_documents") or []),
        "source": "local/fundamental-review-full 中保存的 DeepSeek 历史日常复核",
        "caveat": "任务口径为 entry / holder / risk 三项粗任务；risk 不等于纯负向红线，不能直接改变人工规则或投资动作。",
    }


CURRENT_EVIDENCE_ROLES = {
    "local_current_evidence",
    "official_current_evidence",
    "zcode_current_evidence_extract",
}


def compact_model_review_task(
    task: dict[str, Any],
    rule: dict[str, Any] | None,
    documents: dict[str, dict[str, Any]],
    *,
    baseline_date: str | None = None,
) -> dict[str, Any]:
    """Expose one saved model task while proving whether its evidence is current.

    A task which only cites the main report is historical context, not a current
    verification.  This deliberately does not reinterpret either model's rule.
    """
    evidence_ids = [str(value) for value in task.get("evidence_document_ids") or [] if value]
    def effective_source_role(document: dict[str, Any]) -> str:
        role = str(document.get("source_role") or "unknown")
        if role != "local_current_evidence" or not baseline_date:
            return role
        document_date = str(document.get("document_date") or "")[:10] or None
        if not document_date:
            document_date = extract_document_date(Path(str(document.get("path") or "")), "")
        # The legacy review files can label an older local note as current.
        # Keep it as historical context in the comparison until it is proven
        # newer than the locked main report.
        return role if is_post_baseline_evidence(document_date, baseline_date) else "local_supporting_evidence"

    roles = sorted({effective_source_role(documents.get(document_id) or {}) for document_id in evidence_ids})
    evidence_quality = "current" if any(role in CURRENT_EVIDENCE_ROLES for role in roles) else (
        "historical" if evidence_ids else "missing"
    )
    evidence_lines = []
    for line in task.get("evidence_lines") or []:
        if not isinstance(line, dict):
            continue
        evidence_lines.append(
            {
                "document_id": line.get("document_id"),
                "line_ref": line.get("line_ref"),
                "exact_quote": line.get("exact_quote"),
            }
        )
    return {
        "task_id": task.get("task_id") or (rule or {}).get("task_id") or "unknown",
        "scope_label": (rule or {}).get("scope_label") or task.get("scope_label") or task.get("task_id") or "未命名事项",
        "rule_content": (rule or {}).get("content") or "",
        "status": task.get("status") or "unknown",
        "conclusion": task.get("conclusion") or "",
        "evidence_quality": evidence_quality,
        "evidence_document_ids": evidence_ids,
        "evidence_roles": roles,
        "evidence_dates": sorted(
            {
                str((documents.get(document_id) or {}).get("document_date") or "")[:10]
                or extract_document_date(Path(str((documents.get(document_id) or {}).get("path") or "")), "")
                or ""
                for document_id in evidence_ids
            }
            - {""}
        ),
        "evidence_lines": evidence_lines[:4],
        "missing_codes": task.get("missing_codes") or [],
    }


def model_review_comparison_partition(zcode_tasks: list[dict[str, Any]], deepseek_tasks: list[dict[str, Any]]) -> str:
    """Classify two saved model runs without declaring different rules equivalent."""
    zcode_by_id = {str(task.get("task_id")): task for task in zcode_tasks}
    deepseek_by_id = {str(task.get("task_id")): task for task in deepseek_tasks}
    qualified = lambda task: bool(task) and task.get("evidence_quality") == "current" and task.get("status") not in {"data_insufficient", "unknown", "missing"}
    paired = [
        (zcode_by_id.get(task_id), deepseek_by_id.get(task_id))
        for task_id in sorted(set(zcode_by_id) | set(deepseek_by_id))
    ]
    if any(qualified(left) and qualified(right) and left.get("status") != right.get("status") for left, right in paired):
        return "conflict"
    if any(qualified(left) and qualified(right) for left, right in paired):
        return "consensus"
    if any(qualified(task) for task in zcode_tasks):
        return "zcode_current"
    if any(qualified(task) for task in deepseek_tasks):
        return "deepseek_current"
    return "both_insufficient"


def _model_review_packet(
    payload: dict[str, Any],
    *,
    model_name: str,
    rule_key: str,
    baseline_date: str | None = None,
) -> dict[str, Any]:
    review = payload.get("model_review") if isinstance(payload, dict) else {}
    review = review if isinstance(review, dict) else {}
    documents = {
        str(document.get("document_id")): document
        for document in payload.get("local_evidence_documents") or []
        if isinstance(document, dict) and document.get("document_id")
    }
    rules = {
        str(rule.get("task_id")): rule
        for rule in payload.get(rule_key) or []
        if isinstance(rule, dict) and rule.get("task_id")
    }
    return {
        "model": review.get("model") or model_name,
        "generated_at": payload.get("generated_at"),
        "scope": payload.get("scope") or "",
        "run_status": review.get("status") or "missing",
        "tasks": [
            compact_model_review_task(
                task,
                rules.get(str(task.get("task_id"))),
                documents,
                baseline_date=baseline_date,
            )
            for task in review.get("tasks") or []
            if isinstance(task, dict)
        ],
    }


def model_review_comparison_snapshot(repo_root: Path) -> dict[str, Any]:
    """Create the public ZCode-versus-DeepSeek comparison from saved runs.

    On the VPS the private local review directories are intentionally absent.
    In that case preserve the last generated public snapshot instead of replacing
    it with an empty result during a normal dashboard rebuild.
    """
    deepseek_dir = repo_root / "local" / "fundamental-review-full"
    zcode_dir = repo_root / "local" / "fundamental-review-zcode" / "full-zcode-rules"
    public_path = repo_root / "data" / "investment-dashboard" / "model_review_comparison.json"
    deepseek_paths = {path.stem: path for path in deepseek_dir.glob("*.json")} if deepseek_dir.is_dir() else {}
    zcode_paths = {path.stem: path for path in zcode_dir.glob("*.json")} if zcode_dir.is_dir() else {}
    tickers = sorted(set(deepseek_paths) | set(zcode_paths))
    if not tickers:
        saved = load_json(public_path, {})
        if isinstance(saved, dict) and saved.get("reviews"):
            return saved
        return {
            "schema_version": 1,
            "generated_at": now_iso(),
            "stock_count": 0,
            "summary": {},
            "reviews": [],
            "source": "saved ZCode and DeepSeek review outputs are unavailable",
        }

    reviews = []
    inputs = []
    counts: dict[str, int] = {}
    rules_dir = repo_root / "data" / "investment-dashboard" / "main-report-review-rules"
    baselines = {
        package.get("ticker"): report_baseline_date(package)
        for package in load_rule_packages(rules_dir)
    } if rules_dir.is_dir() else {}
    for ticker in tickers:
        deepseek_path = deepseek_paths.get(ticker)
        zcode_path = zcode_paths.get(ticker)
        deepseek_payload = load_json(deepseek_path, {}) if deepseek_path else {}
        zcode_payload = load_json(zcode_path, {}) if zcode_path else {}
        for path in (deepseek_path, zcode_path):
            if path:
                inputs.append({"path": str(path.relative_to(repo_root)), "sha256": canonical_file_sha256(path)})
        baseline_date = baselines.get(ticker)
        zcode = _model_review_packet(
            zcode_payload,
            model_name="ZCode",
            rule_key="zcode_tasks",
            baseline_date=baseline_date,
        )
        deepseek = _model_review_packet(
            deepseek_payload,
            model_name="DeepSeek",
            rule_key="fixed_tasks",
            baseline_date=baseline_date,
        )
        partition = model_review_comparison_partition(zcode["tasks"], deepseek["tasks"])
        counts[partition] = counts.get(partition, 0) + 1
        reviews.append(
            {
                "ticker": ticker,
                "company": zcode_payload.get("company") or deepseek_payload.get("company") or ticker,
                "partition": partition,
                "zcode": zcode,
                "deepseek": deepseek,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "stock_count": len(reviews),
        "input_fingerprint": canonical_json_sha256(inputs),
        "input_files": inputs,
        "summary": {"partition_counts": counts},
        "reviews": reviews,
        "source": "ZCode independent saved review + DeepSeek saved review; only post-main-report local/official evidence is current evidence.",
        "caveat": "The two models independently derived task wording. A status difference is a review conflict to inspect, not an automatic rule or investment-action change.",
    }


def review_due_at(value: Any, days: int) -> str:
    """Return a displayable due timestamp without inventing a historical run."""
    try:
        base = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        base = datetime.now().astimezone()
    if base.tzinfo is None:
        base = base.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return (base + timedelta(days=days)).isoformat(timespec="seconds")


def packet_layer_run(
    packet: dict[str, Any] | None,
    *,
    layer: str,
    default_reviewer: str,
    rules_fingerprint: str | None,
    migrated_seed: bool = False,
) -> dict[str, Any] | None:
    """Make a saved legacy packet explicit about layer and evidence currency.

    A migrated ZCode packet may occupy the current *daily slot* at the user's
    request, but it must retain its real reviewer and evidence-quality labels.
    It is never rewritten as a DeepSeek result or a current fact.
    """
    if not isinstance(packet, dict) or not packet:
        return None
    tasks = [task for task in packet.get("tasks") or [] if isinstance(task, dict)]
    current_tasks = [task for task in tasks if task.get("evidence_quality") == "current"]
    run_status = str(packet.get("run_status") or "missing")
    evidence_state = "current" if current_tasks else "historical_or_insufficient"
    if run_status not in {"completed", "complete", "success"}:
        status = "error" if run_status not in {"missing", ""} else "data_gap"
    elif current_tasks:
        status = "evidence_ready"
    else:
        status = "data_gap"
    reviewer = str(packet.get("model") or default_reviewer)
    generated_at = packet.get("generated_at")
    return {
        "layer": layer,
        "run_id": f"migrated-{layer}-{str(generated_at or 'undated')}",
        "reviewer": reviewer,
        "model": reviewer,
        "variant": None,
        "generated_at": generated_at,
        # A migration still records which locked-rule version it was attached
        # to, so it expires with a real report change.  It remains explicitly
        # non-comparable with a fresh model run below.
        "rules_fingerprint": rules_fingerprint,
        "evidence_fingerprint": None,
        "run_status": run_status,
        "status": status,
        "label": "已保存日常复核" if current_tasks else "已保存复核：证据不足 / 历史",
        "evidence_state": evidence_state,
        "current_evidence_count": len(current_tasks),
        "tasks": tasks,
        "migrated_seed": migrated_seed,
        "comparison_eligible": not migrated_seed,
        "source": "迁移的已保存复核结果；保留原始复核者与证据状态。",
        "due_at": review_due_at(generated_at, DAILY_REVIEW_DUE_DAYS if layer == "daily" else DEEP_REVIEW_DUE_DAYS),
    }


def normalized_layer_status(value: Any) -> str:
    """Map archived review vocabulary into the public layer state contract."""
    raw_status = str(value or "data_gap")
    return {
        "warning": "attention",
        "data_insufficient": "data_gap",
        "waiting_official_disclosure": "waiting_evidence",
        "rule_stale": "stale_rules",
    }.get(raw_status, raw_status)


def codex_layer_run(
    direct: dict[str, Any] | None,
    *,
    rules_fingerprint: str | None,
) -> dict[str, Any] | None:
    if not isinstance(direct, dict) or not direct:
        return None
    generated_at = direct.get("reviewed_at")
    raw_status = str(direct.get("status") or "data_gap")
    # The older direct-review archive used a slightly different vocabulary.
    # Normalize only the dashboard state; retain its human-readable label and
    # source intact so a legacy warning is not misreported as a fresh redline.
    status = normalized_layer_status(raw_status)
    return {
        "layer": "deep",
        "run_id": f"codex-direct-{str(generated_at or 'undated')}",
        "reviewer": str(direct.get("reviewer") or "Codex 直接复核（未调用模型）"),
        "model": "Codex 直接复核（未调用模型）",
        "variant": None,
        "generated_at": generated_at,
        "rules_fingerprint": rules_fingerprint,
        "evidence_fingerprint": None,
        "run_status": "completed",
        "status": status,
        "label": direct.get("label") or status,
        "evidence_state": "current" if direct.get("evidence_count") else "historical_or_insufficient",
        "current_evidence_count": direct.get("evidence_count") or 0,
        "tasks": [],
        "migrated_seed": True,
        "source": direct.get("source_statement") or "Codex 直接复核归档。",
        "due_at": review_due_at(generated_at, DEEP_REVIEW_DUE_DAYS),
        "redline_count": direct.get("redline_count") or 0,
        "warning_count": direct.get("warning_count") or 0,
        "data_gaps": direct.get("data_gaps") or [],
    }


def stored_layer_run(path: Path, *, layer: str, rules_fingerprint: str) -> dict[str, Any] | None:
    """Load a completed atomic layer result only when it matches active rules."""
    payload = load_json(path, {})
    if not isinstance(payload, dict) or payload.get("layer") != layer:
        return None
    if payload.get("rules_fingerprint") != rules_fingerprint:
        return None
    payload["status"] = normalized_layer_status(payload.get("status"))
    return payload


def layer_comparison(daily: dict[str, Any] | None, deep: dict[str, Any] | None) -> dict[str, str]:
    """A comparison is an alert only; it never changes a locked rule or action."""
    if not daily or not deep:
        return {"state": "not_available", "label": "缺少其中一层结果"}
    if daily.get("migrated_seed") or deep.get("migrated_seed"):
        return {"state": "not_comparable", "label": "含迁移记录，等待同版新复核后再比较"}
    daily_fingerprint = daily.get("rules_fingerprint")
    deep_fingerprint = deep.get("rules_fingerprint")
    if not daily_fingerprint or not deep_fingerprint or daily_fingerprint != deep_fingerprint:
        return {"state": "not_comparable", "label": "规则版本不同或历史迁移结果，不能直接比较"}
    if daily.get("status") == "error" or deep.get("status") == "error":
        return {"state": "not_comparable", "label": "存在失败复核，等待有效结果"}
    if daily.get("status") != deep.get("status"):
        return {"state": "different", "label": "两层结果不同，需查看证据"}
    return {"state": "aligned", "label": "两层状态一致"}


def merge_saved_layer_snapshot(snapshot: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
    """Carry runtime review layers across a release without carrying stale rules.

    The static release builder does not own the VPS runtime directory.  It may
    reuse a saved layer only when the exact locked main-report hash still
    matches; a changed report always falls back to the newly built stale state.
    """
    if not isinstance(saved, dict) or int(saved.get("schema_version") or 0) < PUBLIC_SNAPSHOT_VERSION:
        return snapshot
    saved_by_ticker = {
        str(row.get("ticker")): row
        for row in (saved.get("reviews") or [])
        if isinstance(row, dict) and row.get("ticker")
    }
    for row in snapshot.get("reviews") or []:
        previous = saved_by_ticker.get(str(row.get("ticker")))
        if not previous or row.get("rule_state") != "active":
            continue
        current_hash = (row.get("main_report") or {}).get("canonical_sha256")
        previous_hash = (previous.get("main_report") or {}).get("canonical_sha256")
        if not current_hash or current_hash != previous_hash:
            continue
        for layer in ("daily", "deep"):
            if isinstance(previous.get(layer), dict):
                row[layer] = previous[layer]
        row["layer_comparison"] = layer_comparison(
            (row.get("daily") or {}).get("current"),
            (row.get("deep") or {}).get("current"),
        )
    return snapshot


def public_review_snapshot(
    rules_dir: Path,
    output_dir: Path,
    comparison: dict[str, Any] | None = None,
    legacy_dir: Path | None = None,
    layers_dir: Path | None = None,
) -> dict[str, Any]:
    generated_at = now_iso()
    repo_root = rules_dir.resolve().parents[2]
    next_check_at = (datetime.now().astimezone() + timedelta(days=DAILY_REVIEW_DUE_DAYS)).isoformat(timespec="seconds")
    rules_by_ticker = {package["ticker"]: package for package in load_rule_packages(rules_dir)}
    codex_archive = load_json(rules_dir.parent / "codex_direct_manual_review.json", {})
    codex_by_ticker = {
        str(row.get("ticker")): row
        for row in (codex_archive.get("reviews") or [])
        if isinstance(row, dict) and row.get("ticker")
    }
    legacy_model_snapshot = model_review_comparison_snapshot(repo_root)
    legacy_model_by_ticker = {
        str(row.get("ticker")): row
        for row in (legacy_model_snapshot.get("reviews") or [])
        if isinstance(row, dict) and row.get("ticker")
    }
    layers_dir = layers_dir or output_dir.parent / "fundamental-review-layers"
    rows = []
    status_counts: dict[str, int] = {}
    for ticker, package in sorted(rules_by_ticker.items()):
        result = load_json(output_dir / f"{ticker}.json", {})
        price_context = result.get("price_context") if isinstance(result, dict) else None
        if not isinstance(price_context, dict):
            price_context = read_price_context(repo_root, ticker)
        legacy_payload = load_json(legacy_dir / f"{ticker}.json", {}) if legacy_dir else {}
        legacy_daily = compact_legacy_daily_review(legacy_payload)
        result_is_current = (
            result.get("protocol_version") == PROTOCOL_VERSION
            and result.get("rules_fingerprint") == package.get("rules_fingerprint")
        )
        if not result_is_current:
            result = {}
        reviewable_rule_count = sum(
            rule.get("reviewable") is True for rule in package.get("active_rules") or []
        )
        default_status = (
            "stale_rules"
            if package.get("rule_state") == "stale"
            else "no_rules" if reviewable_rule_count == 0 else "waiting_evidence"
        )
        default_label = {
            "stale_rules": "主报告已变化",
            "no_rules": "暂无可复核经营规则",
            "waiting_evidence": "等待新证据",
        }[default_status]
        results_by_id = {
            row.get("rule_id"): row
            for row in ((result.get("model_review") or {}).get("rules") or [])
            if isinstance(row, dict)
        }
        public_rules = []
        for rule in package.get("active_rules") or []:
            saved_result = results_by_id.get(rule.get("rule_id"))
            # Older saved results used the coarse raw group.  Recalculate only
            # their display effect so a positive confirmation cannot remain a
            # false "redline hit" after this semantic fix.
            if isinstance(saved_result, dict):
                saved_result = {
                    **saved_result,
                    "review_effect": effect_for_rule(
                        rule,
                        str(saved_result.get("truth_state") or "unknown"),
                    ),
                }
            public_rules.append(
                {
                    **rule,
                    "semantic_group": semantic_group_for_rule(rule),
                    "semantic_relation": semantic_relation_for_rule(rule),
                    "result": saved_result,
                }
            )
        current_results = [rule["result"] for rule in public_rules if isinstance(rule.get("result"), dict)]
        if current_results and isinstance((result.get("model_review") or {}), dict) and (
            result.get("model_review") or {}
        ).get("status") == "completed":
            summary = aggregate_review_status(package, current_results)
        else:
            summary = result.get("summary") or {
                "status": default_status,
                "label": default_label,
                "redline_count": 0,
                "warning_count": 0,
                "positive_count": 0,
                "unknown_count": reviewable_rule_count,
                "missing_requirements": sorted(
                    {
                        requirement
                        for rule in package.get("active_rules") or []
                        if rule.get("reviewable") is True
                        for requirement in rule.get("evidence_requirement") or []
                    }
                ),
            }
        status = str(summary.get("status") or "waiting_evidence")
        manual_status = (
            "stale"
            if package.get("rule_state") == "stale"
            else "no_rules" if not public_rules else "active"
        )
        manual_label = {
            "active": "人工锁定规则有效",
            "stale": "主报告已变化，待人工更新规则",
            "no_rules": "暂无人工锁定经营规则",
        }[manual_status]
        legacy_models = legacy_model_by_ticker.get(ticker) or {}
        saved_daily = stored_layer_run(
            layers_dir / "daily" / f"{ticker}.json",
            layer="daily",
            rules_fingerprint=package.get("rules_fingerprint"),
        )
        # The user selected ZCode as the current seed of the daily layer.  It
        # remains explicitly labelled as ZCode until a newer DeepSeek run for
        # this exact stock atomically replaces it.
        daily_current = saved_daily or packet_layer_run(
            legacy_models.get("zcode"),
            layer="daily",
            default_reviewer="ZCode",
            rules_fingerprint=package.get("rules_fingerprint"),
            migrated_seed=True,
        )
        saved_deep = stored_layer_run(
            layers_dir / "deep" / f"{ticker}.json",
            layer="deep",
            rules_fingerprint=package.get("rules_fingerprint"),
        )
        deep_current = saved_deep or codex_layer_run(
            codex_by_ticker.get(ticker),
            rules_fingerprint=package.get("rules_fingerprint"),
        )
        daily_history = []
        deepseek_history = packet_layer_run(
            legacy_models.get("deepseek"),
            layer="daily",
            default_reviewer="DeepSeek",
            rules_fingerprint=package.get("rules_fingerprint"),
            migrated_seed=True,
        )
        if deepseek_history:
            daily_history.append(deepseek_history)
        if saved_daily and legacy_models.get("zcode"):
            previous_zcode = packet_layer_run(
                legacy_models.get("zcode"),
                layer="daily",
                default_reviewer="ZCode",
                rules_fingerprint=package.get("rules_fingerprint"),
                migrated_seed=True,
            )
            if previous_zcode:
                daily_history.append(previous_zcode)
        deep_history = []
        if saved_deep and codex_by_ticker.get(ticker):
            previous_codex = codex_layer_run(
                codex_by_ticker.get(ticker),
                rules_fingerprint=package.get("rules_fingerprint"),
            )
            if previous_codex:
                deep_history.append(previous_codex)
        # This deliberately remains separate from the manual layer.  A model
        # result is a point-in-time evidence check, never an authority to alter
        # a threshold, a red line, or the main-report judgment.
        model_review = result.get("model_review") if isinstance(result, dict) else None
        has_current_model_result = isinstance(model_review, dict) and model_review.get("status") == "completed"
        if has_current_model_result:
            routine_status = status
            routine_label = summary.get("label") or default_label
            routine_model = model_review.get("model") or "DeepSeek 日常核验"
            routine_generated_at = result.get("generated_at")
            routine_evidence_count = result.get("current_evidence_count", 0)
            routine_evidence_date = result.get("latest_evidence_date")
        elif legacy_daily:
            # We have a real saved daily model run, but it predates the strict
            # atomic-rule protocol.  Show it rather than hiding it, while
            # retaining the newer run's error/waiting state as context.
            routine_status = "historical_review"
            routine_label = "上一轮日常复核（历史）"
            routine_model = legacy_daily["model"]
            routine_generated_at = legacy_daily.get("generated_at")
            routine_evidence_count = legacy_daily.get("local_evidence_count", 0)
            routine_evidence_date = None
        else:
            routine_status = status
            routine_label = summary.get("label") or default_label
            routine_model = "DeepSeek 日常核验"
            routine_generated_at = result.get("generated_at")
            routine_evidence_count = result.get("current_evidence_count", 0)
            routine_evidence_date = result.get("latest_evidence_date")
        status_counts[routine_status] = status_counts.get(routine_status, 0) + 1
        rows.append(
            {
                "company": package.get("company"),
                "ticker": ticker,
                "rule_state": package.get("rule_state"),
                "main_report": package.get("main_report"),
                "summary": summary,
                "generated_at": result.get("generated_at"),
                "message": result.get("message"),
                "latest_evidence_date": result.get("latest_evidence_date"),
                "current_evidence_count": result.get("current_evidence_count", 0),
                "price_context": price_context,
                "evidence_documents": result.get("evidence_documents") or [],
                "last_probe_at": generated_at,
                "next_check_at": next_check_at,
                "rules": public_rules,
                "audit_candidates": package.get("audit_candidates") or [],
                "manual": {
                    "authority": "human_locked",
                    "status": manual_status,
                    "label": manual_label,
                    "reviewed_at": (package.get("main_report") or {}).get("reviewed_at"),
                    "rule_count": len(public_rules),
                    "reviewable_rule_count": reviewable_rule_count,
                    "audit_candidate_count": len(package.get("audit_candidates") or []),
                    "source": "人工主报告裁决与锁定规则",
                    "codex_direct": codex_by_ticker.get(ticker),
                },
                "routine": {
                    "status": routine_status,
                    "label": routine_label,
                    "reviewer": routine_model,
                    "run_state": (model_review or {}).get("status") or ("historical_saved" if legacy_daily else ("not_run" if not result else "no_result")),
                    "generated_at": routine_generated_at,
                    "latest_evidence_date": routine_evidence_date,
                    "current_evidence_count": routine_evidence_count,
                    "source": legacy_daily.get("source") if legacy_daily else "主报告之后的新证据；本地资料优先，官方披露补充",
                    "message": result.get("message"),
                    "legacy_daily": legacy_daily,
                    "strict_incremental": {
                        "status": status,
                        "label": summary.get("label") or default_label,
                        "generated_at": result.get("generated_at"),
                        "current_evidence_count": result.get("current_evidence_count", 0),
                        "latest_evidence_date": result.get("latest_evidence_date"),
                        "price_context": price_context,
                        "message": result.get("message"),
                    },
                },
                "daily": {
                    "current": daily_current,
                    "history": daily_history,
                    "due_at": (daily_current or {}).get("due_at") or next_check_at,
                    "policy": "日常层由 DeepSeek 手动复核；当前 ZCode 仅为迁移的日常记录，直到该股新的 DeepSeek 结果覆盖。",
                },
                "deep": {
                    "current": deep_current,
                    "history": deep_history,
                    "due_at": (deep_current or {}).get("due_at") or review_due_at(generated_at, DEEP_REVIEW_DUE_DAYS),
                    "policy": "深度层由用户每次指定模型与推理档位手动复核；不固定为某一模型。",
                },
                "layer_comparison": layer_comparison(daily_current, deep_current),
            }
        )
    return {
        "schema_version": PUBLIC_SNAPSHOT_VERSION,
        "generated_at": generated_at,
        "next_check_at": next_check_at,
        "source": "human_locked_rules + migrated_zcode_daily + saved_deepseek_daily_history + codex_deep + atomic_layer_runs",
        "status_counts": status_counts,
        "stock_count": len(rows),
        "comparison": comparison.get("summary") if isinstance(comparison, dict) else None,
        "reviews": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--rules-dir", type=Path, default=Path("data/investment-dashboard/main-report-review-rules"))
    parser.add_argument("--output-dir", type=Path, default=Path("local/fundamental-review-current"))
    parser.add_argument("--legacy-dir", type=Path, default=Path("local/fundamental-review-full"))
    parser.add_argument("--migrate-rules", action="store_true")
    parser.add_argument("--migrate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-official", action="store_true")
    parser.add_argument("--ticker", action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--write-comparison", action="store_true")
    parser.add_argument("--write-model-comparison-snapshot", action="store_true")
    parser.add_argument("--write-protocol-findings", action="store_true")
    parser.add_argument("--write-public-snapshot", action="store_true")
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    rules_dir = args.rules_dir if args.rules_dir.is_absolute() else repo_root / args.rules_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
    legacy_dir = args.legacy_dir if args.legacy_dir.is_absolute() else repo_root / args.legacy_dir
    if args.migrate_rules:
        print(json.dumps(migrate_rule_packages(repo_root, rules_dir), ensure_ascii=False, indent=2))
        if args.migrate_only:
            return 0
    if args.snapshot_only:
        comparison = comparison_snapshot(repo_root)
        if args.write_comparison:
            atomic_write_json(output_dir / "comparison-current.json", comparison)
            atomic_write_text(output_dir / "对照报告-current.md", render_comparison_markdown(comparison))
        if args.write_public_snapshot:
            snapshot = public_review_snapshot(rules_dir, output_dir, comparison, legacy_dir)
            atomic_write_json(repo_root / "data" / "investment-dashboard" / "main_report_review.json", snapshot)
            atomic_write_json(repo_root / "site" / "data" / "main_report_review.json", snapshot)
        if args.write_model_comparison_snapshot:
            model_snapshot = model_review_comparison_snapshot(repo_root)
            atomic_write_json(repo_root / "data" / "investment-dashboard" / "model_review_comparison.json", model_snapshot)
            atomic_write_json(repo_root / "site" / "data" / "model_review_comparison.json", model_snapshot)
        print(json.dumps({"generated_at": now_iso(), "snapshot_only": True}, ensure_ascii=False, indent=2))
        return 0
    run_status = run_incremental(
        repo_root,
        rules_dir,
        output_dir,
        tickers={str(value).upper() for value in args.ticker} or None,
        include_official=args.include_official,
        dry_run=args.dry_run,
        workers=args.workers,
    )
    comparison = comparison_snapshot(repo_root)
    if args.write_comparison and not args.dry_run:
        atomic_write_json(output_dir / "comparison-current.json", comparison)
        atomic_write_text(output_dir / "对照报告-current.md", render_comparison_markdown(comparison))
    if args.write_public_snapshot and not args.dry_run:
        snapshot = public_review_snapshot(rules_dir, output_dir, comparison, legacy_dir)
        atomic_write_json(repo_root / "data" / "investment-dashboard" / "main_report_review.json", snapshot)
        atomic_write_json(repo_root / "site" / "data" / "main_report_review.json", snapshot)
    if args.write_model_comparison_snapshot and not args.dry_run:
        model_snapshot = model_review_comparison_snapshot(repo_root)
        atomic_write_json(repo_root / "data" / "investment-dashboard" / "model_review_comparison.json", model_snapshot)
        atomic_write_json(repo_root / "site" / "data" / "model_review_comparison.json", model_snapshot)
    if args.write_protocol_findings and not args.dry_run:
        atomic_write_json(output_dir / "protocol-findings-current.json", protocol_findings_snapshot(output_dir))
    print(json.dumps(run_status, ensure_ascii=False, indent=2))
    return 1 if run_status["counts"]["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
