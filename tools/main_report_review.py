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
PROTOCOL_VERSION = "main-report-review-v2.2"
RULE_GROUPS = {"entry", "holder", "improvement", "redline"}
RULE_POLARITIES = {"positive", "negative", "monitoring"}
RULE_STATES = {"active", "stale", "pending_manual_confirmation", "archived"}
SCHEDULE_TYPES = {"price", "filing", "recurring_filing", "event"}
TRUTH_STATES = {"met", "not_met", "unknown", "not_due"}
REVIEW_EFFECTS = {"positive", "neutral", "warning", "redline"}
MISSING_CODES = {
    "no_current_value",
    "no_comparison",
    "no_threshold",
    "no_official_source",
    "no_event_confirmation",
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
    if re.search(r"任一|任意|之一|或者|或", text):
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
            "redline_count": sum(rule.get("group") == "redline" for rule in active_rules),
            "improvement_count": sum(rule.get("group") == "improvement" for rule in active_rules),
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
        source_catalog[str(row.get("document_id") or "")] = {
            "path": relative,
            "document_date": extract_document_date(source_path, raw),
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
            role = manifest_roles[relative]
        elif is_main:
            role = "main_report_reference"
        else:
            role = (
                "local_current_evidence"
                if document_date and baseline and document_date > baseline
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


def _download_official_pdf(url: str) -> tuple[str, str, int]:
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
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text[:18000], hashlib.sha256(completed.stdout).hexdigest(), len(reader.pages)


def collect_official_evidence(package: dict[str, Any], *, lookback_days: int = 120) -> list[dict[str, Any]]:
    ticker = str(package.get("ticker") or "")
    company = str(package.get("company") or "")
    rows = sentiment_snapshot.fetch_cninfo_company_news(
        {"company": company, "ticker": ticker, "market": "A股"},
        display_name=company,
        cutoff=datetime.now().astimezone(),
        lookback_days=lookback_days,
        news_limit=100,
        retrieval_window_type="main_report_incremental_review",
    )
    selected = [
        row
        for row in rows
        if any(token in str(row.get("title") or "") for token in OFFICIAL_TITLE_TOKENS)
    ][:3]
    documents: list[dict[str, Any]] = []
    for row in selected:
        try:
            content, sha256, page_count = _download_official_pdf(str(row.get("url") or ""))
        except Exception:
            continue
        published = str(row.get("published_at") or "")
        documents.append(
            {
                "document_id": f"official_{len(documents) + 1}",
                "path": str(row.get("url") or ""),
                "title": row.get("title"),
                "source_role": "official_current_evidence",
                "document_date": published[:10] or None,
                "canonical_sha256": sha256,
                "page_count": page_count,
                "content": content,
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
    group = rule.get("group")
    if truth_state in {"unknown", "not_due"}:
        return "neutral"
    if group == "redline":
        return "redline" if truth_state == "met" else "neutral"
    if group == "improvement":
        return "positive" if truth_state == "met" else "neutral"
    if group == "holder":
        return "warning" if truth_state == "not_met" else "neutral"
    return "positive" if truth_state == "met" else "neutral"


def review_rules_with_model(
    package: dict[str, Any],
    documents: list[dict[str, Any]],
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
                "relation",
                "metrics",
                "operator",
                "threshold",
                "periods",
                "evidence_requirement",
            )
        }
        for rule in active_rules
    }
    document_catalog = {
        document["document_id"]: {
            "path": document.get("path"),
            "source_role": document.get("source_role"),
            "document_date": document.get("document_date"),
            "content": document.get("content"),
        }
        for document in documents
    }
    config = opportunity_review.model_config("scan_flash")
    system = (
        "你是主报告锁定规则的证据核验员。规则由人工锁定，你无权新增、删除、修改、放宽、"
        "重解释任何条件或阈值。main_report_reference 只能证明规则来源，不能证明当前状态。"
        "只有 local_current_evidence、zcode_current_evidence_extract 或 official_current_evidence 可用于 met/not_met；"
        "zcode_current_evidence_extract 只复用旧任务抽取的当前值与原文证据，旧任务的状态结论无效；"
        "local_supporting_evidence 也不能单独证明当前状态。缺少当前值、对比期或事件确认必须 unknown。"
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
                        "evidence_document_ids": "最多3个 document_catalog id",
                        "evidence_lines": "最多3项：document_id,line_ref,exact_quote",
                        "missing_codes": "only no_current_value/no_comparison/no_threshold/no_official_source/no_event_confirmation",
                    }
                ],
                "rule_update": "must be manual_only",
            },
            "task_catalog": task_catalog,
            "document_catalog": document_catalog,
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
    response, reasoning = opportunity_review.request_json(config, system=system, user=user)
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
        if "official_source" in requirements and not any(
            document_catalog[value].get("source_role") == "official_current_evidence"
            for value in current_ids
        ):
            inferred_missing.append("no_official_source")
        if "event_confirmation" in requirements and not evidence_lines:
            inferred_missing.append("no_event_confirmation")
        for code in inferred_missing:
            if code not in missing_codes:
                missing_codes.append(code)
        # A compound rule is inconclusive when any required component is absent.
        # This intentionally fails closed for both met and not_met.
        if truth_state in {"met", "not_met"} and missing_codes:
            truth_state = "unknown"
        rule = next(rule for rule in active_rules if rule["rule_id"] == rule_id)
        by_id[rule_id] = {
            "rule_id": rule_id,
            "truth_state": truth_state,
            "review_effect": effect_for_rule(rule, truth_state),
            "current_value": compact_text(raw.get("current_value")),
            "comparison": compact_text(raw.get("comparison")),
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
                    "evidence_document_ids": [],
                    "evidence_lines": [],
                    "missing_codes": ["no_current_value"],
                },
            )
        )
    return {
        "status": "completed",
        "rule_update": "manual_only",
        "model": config.model,
        "reasoning": reasoning,
        "rules": results,
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
) -> dict[str, Any]:
    fingerprint = input_fingerprint(package, documents)
    current_documents = [
        document
        for document in documents
        if document.get("source_role") in {"local_current_evidence", "official_current_evidence"}
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
        payload = result_payload(package, documents, None, status="stale_rules", message="主报告内容已变化，旧规则只读留档，等待人工重建")
        if not dry_run:
            atomic_write_json(output_path, payload)
        return ticker, "stale", payload
    reviewable = [rule for rule in package.get("active_rules") or [] if rule.get("reviewable") is True]
    if not reviewable:
        payload = result_payload(package, documents, None, status="no_rules", message="当前只有价格规则，由人工复核价格分区处理")
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
        payload = result_payload(package, documents, None, status="waiting_evidence", message="没有主报告基线之后的新证据，本次不调用模型")
        if not dry_run:
            atomic_write_json(output_path, payload)
        return ticker, "waiting", payload
    if dry_run:
        return ticker, "due", None
    try:
        model_review = review_rules_with_model(package, documents)
        payload = result_payload(package, documents, model_review)
    except Exception as exc:
        payload = result_payload(package, documents, None, status="error", message=str(exc))
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


def public_review_snapshot(
    rules_dir: Path,
    output_dir: Path,
    comparison: dict[str, Any] | None = None,
    legacy_dir: Path | None = None,
) -> dict[str, Any]:
    generated_at = now_iso()
    next_check_at = (datetime.now().astimezone() + timedelta(days=3)).isoformat(timespec="seconds")
    rules_by_ticker = {package["ticker"]: package for package in load_rule_packages(rules_dir)}
    rows = []
    status_counts: dict[str, int] = {}
    for ticker, package in sorted(rules_by_ticker.items()):
        result = load_json(output_dir / f"{ticker}.json", {})
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
        results_by_id = {
            row.get("rule_id"): row
            for row in ((result.get("model_review") or {}).get("rules") or [])
            if isinstance(row, dict)
        }
        public_rules = []
        for rule in package.get("active_rules") or []:
            public_rules.append(
                {
                    **rule,
                    "result": results_by_id.get(rule.get("rule_id")),
                }
            )
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
                        "message": result.get("message"),
                    },
                },
            }
        )
    return {
        "schema_version": 4,
        "generated_at": generated_at,
        "next_check_at": next_check_at,
        "source": "human_locked_rules + saved_deepseek_daily_review + strict_incremental_evidence",
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
    print(json.dumps(run_status, ensure_ascii=False, indent=2))
    return 1 if run_status["counts"]["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
