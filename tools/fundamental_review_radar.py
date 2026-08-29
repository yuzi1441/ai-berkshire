#!/usr/bin/env python3
"""Run one source-backed, stock-specific fundamental review radar.

This is deliberately separate from price zones, Checklist, sentiment, technical
signals, and the existing manual execution review.  It evaluates only the
explicit conditions supplied in a company rule file and writes an auditable
local snapshot.  The pilot currently supports 东方电子 (000682.SZ), while the
input and result schema are reusable for later per-stock rule packages.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pypdf import PdfReader

# This file runs both as ``python tools/...`` and as an imported test module.
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import opportunity_review
import sentiment_snapshot


EASTMONEY_URL = "https://datacenter.eastmoney.com/securities/api/data/get"
CNINFO_H1_URL = "https://static.cninfo.com.cn/finalpage/2026-08-20/1225481429.PDF"
ALLOWED_SEMANTIC_STATES = {"not_breached", "warning", "breached", "inconclusive"}
ALLOWED_LOCAL_EVIDENCE_AVAILABILITY = {"verified", "partial", "not_disclosed"}
OFFICIAL_EVIDENCE_TITLE_TOKENS = ("半年度报告", "年度报告", "季度报告", "投资者关系", "调研", "订单", "中标", "项目", "产业园")
ALLOWED_TASK_REVIEW_STATUSES = {"verified", "not_triggered", "triggered", "data_insufficient"}
ALLOWED_TASK_MISSING_CODES = {
    "no_current_value",
    "no_comparison",
    "no_threshold",
    "no_official_source",
    "no_event_confirmation",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def curl_bytes(url: str, *, params: dict[str, str] | None = None) -> bytes:
    if params:
        url = f"{url}?{urlencode(params)}"
    completed = subprocess.run(
        ["curl", "-fsSL", "--noproxy", "*", "-H", "User-Agent: Mozilla/5.0", url],
        check=True,
        capture_output=True,
        timeout=45,
    )
    return completed.stdout


def curl_json(url: str, *, params: dict[str, str]) -> dict[str, Any]:
    return json.loads(curl_bytes(url, params=params).decode("utf-8"))


def number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentage_error(left: float | None, right: float | None) -> float | None:
    if left is None or right is None or left == 0:
        return None
    return abs(left - right) / abs(left) * 100


def fetch_eastmoney_financials(ticker: str) -> list[dict[str, Any]]:
    code, market = ticker.split(".", 1)
    payload = curl_json(
        EASTMONEY_URL,
        params={
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "ALL",
            "filter": f'(SECUCODE="{code}.{market}")',
            "p": "1",
            "ps": "20",
            "sr": "-1",
            "st": "REPORT_DATE",
            "source": "HSF10",
            "client": "PC",
        },
    )
    records = payload.get("result", {}).get("data", [])
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"东方财富未返回 {ticker} 财务记录")
    return records


def normalise_financial_record(row: dict[str, Any]) -> dict[str, Any]:
    net_profit = number(row.get("PARENTNETPROFIT"))
    eps = number(row.get("EPSJB"))
    per_share_ocf = number(row.get("MGJYXJJE"))
    shares = net_profit / eps if net_profit is not None and eps not in (None, 0) else None
    return {
        "period": str(row.get("REPORT_DATE_NAME") or row.get("REPORT_DATE") or ""),
        "report_date": str(row.get("REPORT_DATE") or "")[:10],
        "report_type": str(row.get("REPORT_TYPE") or ""),
        "revenue": number(row.get("TOTALOPERATEREVE")),
        "net_profit": net_profit,
        "deducted_profit": number(row.get("KCFJCXSYJLR")),
        "deducted_profit_yoy": number(row.get("KCFJCXSYJLRTZ")),
        "gross_margin": number(row.get("XSMLL")),
        "operating_cash_flow": per_share_ocf * shares if per_share_ocf is not None and shares is not None else None,
        "implied_shares": shares,
        "source": "eastmoney",
    }


def find_period(records: list[dict[str, Any]], label: str) -> dict[str, Any]:
    for row in records:
        if row["period"] == label:
            return row
    raise RuntimeError(f"东方财富缺少 {label} 数据")


def extract_cninfo_h1(url: str) -> tuple[dict[str, float], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="fundamental-review-") as directory:
        pdf_path = Path(directory) / "filing.pdf"
        pdf_bytes = curl_bytes(url)
        pdf_path.write_bytes(pdf_bytes)
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

    patterns = {
        "revenue": r"营业收入（元）\s*([\d,.-]+)\s+([\d,.-]+)\s+([\d.-]+)%",
        "net_profit": r"归属于上市公司股东的净利润（元）\s*([\d,.-]+)\s+([\d,.-]+)\s+([\d.-]+)%",
        "deducted_profit": r"损益的净利润（元）\s*([\d,.-]+)\s+([\d,.-]+)\s+([\d.-]+)%",
        "operating_cash_flow": r"经营活动产生的现金流量净额（元）\s*([\d,.-]+)\s+([\d,.-]+)\s+([\d.-]+)%",
    }
    values: dict[str, float] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.S)
        if not match:
            raise RuntimeError(f"巨潮中报未找到字段：{key}")
        values[key] = float(match.group(1).replace(",", ""))
        if key == "deducted_profit":
            values["deducted_profit_yoy"] = float(match.group(3))

    # The official filing has a product-line table.  These two lines are the
    # exact items named by the main report's low-margin mix redline.
    segments: list[dict[str, Any]] = []
    for name in ("智能配用电业务", "新能源及储能业务", "综合能源及虚拟电厂"):
        match = re.search(
            rf"{name}\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d.-]+)%\s+([\d.-]+)%\s+([\d.-]+)%",
            text,
        )
        if match:
            segments.append(
                {
                    "name": name,
                    "revenue": float(match.group(1).replace(",", "")),
                    "gross_margin": float(match.group(3)),
                    "revenue_yoy": float(match.group(4)),
                    "gross_margin_yoy_change_pct_point": float(match.group(5)),
                }
            )
    for segment in segments:
        segment["revenue_share"] = segment["revenue"] / values["revenue"] * 100
        name = segment["name"]
        share_match = re.search(
            rf"{name}\s+([\d,.-]+)\s+([\d.-]+)%\s+([\d,.-]+)\s+([\d.-]+)%\s+([\d.-]+)%",
            text,
        )
        if share_match:
            segment["revenue_share"] = float(share_match.group(2))
            segment["previous_revenue_share"] = float(share_match.group(4))

    return values, {
        "url": url,
        "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "page_count": page_count,
        "segments": segments,
    }


def fetch_quote(ticker: str) -> dict[str, Any]:
    code, market = ticker.split(".", 1)
    prefix = "sh" if market == "SH" else "sz"
    raw = curl_bytes(f"https://qt.gtimg.cn/q={prefix}{code}").decode("gbk", errors="replace")
    match = re.search(r'"(.*)"', raw)
    if not match:
        raise RuntimeError(f"腾讯行情未返回 {ticker}")
    fields = match.group(1).split("~")
    if len(fields) < 34:
        raise RuntimeError(f"腾讯行情格式异常：{ticker}")
    return {
        "name": fields[1],
        "price": number(fields[3]),
        "timestamp": fields[30],
        "source": "tencent_quote",
    }


def collect_latest_local_evidence(repo_root: Path) -> list[dict[str, Any]]:
    """Collect recent company evidence for the model, never for rule replacement.

    Rule changes remain a manual operation bound to ``main_report``.  This
    collection is deliberately limited to post-report fundamental reviews and
    source notes; it excludes technical analysis, Checklist, sentiment, and
    execution-review material.
    """
    company_dir = repo_root / "reports" / "东方电子"
    tracker = sorted(company_dir.glob("东方电子-thesis-tracker-*.md"), reverse=True)
    candidates = [
        *(tracker[:1]),
        company_dir / "东方电子-thesis.md",
        company_dir / "sources" / "2026_investor_qa_clean.txt",
    ]
    documents: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        # Source notes can be long.  Preserve the parts relevant to the rules
        # under review, with line references, instead of making a model guess.
        lines = raw.splitlines()
        if path.name.endswith("investor_qa_clean.txt"):
            selected = [
                f"L{index + 1}: {line}"
                for index, line in enumerate(lines)
                if any(token in line for token in ("海外", "订单", "合同", "中标", "回款", "虚拟电厂", "应收"))
            ]
            text = "\n".join(selected[:80])
        else:
            text = "\n".join(f"L{index + 1}: {line}" for index, line in enumerate(lines))[:18000]
        documents.append(
            {
                "document_id": f"local_{len(documents) + 1}",
                "path": str(path.relative_to(repo_root)),
                "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "content": text,
                "purpose": "只作为复核证据；不得修改主报告规则。",
            }
        )
    if not documents:
        raise RuntimeError("未找到东方电子可供复核模型读取的本地基本面资料")
    return documents


def extract_pdf_evidence(url: str, *, max_chars: int = 18000) -> tuple[str, str, int]:
    """Read an official PDF into a bounded, auditable evidence payload."""
    with tempfile.TemporaryDirectory(prefix="fundamental-review-evidence-") as directory:
        pdf_path = Path(directory) / "official.pdf"
        payload = curl_bytes(url)
        pdf_path.write_bytes(payload)
        reader = PdfReader(str(pdf_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text[:max_chars], hashlib.sha256(payload).hexdigest(), len(reader.pages)


def collect_recent_official_evidence(
    ticker: str,
    *,
    cutoff: datetime | None = None,
    lookback_days: int = 60,
) -> list[dict[str, Any]]:
    """Use recent CNINFO disclosures as evidence, never as a rule replacement.

    This is deliberately a second evidence layer.  The main-report rule package
    remains locked unless the user manually updates it through a separate action.
    """
    cutoff = cutoff or datetime.now().astimezone()
    rows = sentiment_snapshot.fetch_cninfo_company_news(
        {"company": "东方电子", "ticker": ticker, "market": "A股"},
        display_name="东方电子",
        cutoff=cutoff,
        lookback_days=lookback_days,
        news_limit=100,
        retrieval_window_type="fundamental_review_pilot",
    )
    selected = [
        row for row in rows
        if any(token in str(row.get("title") or "") for token in OFFICIAL_EVIDENCE_TITLE_TOKENS)
    ][:5]
    documents: list[dict[str, Any]] = []
    for row in selected:
        try:
            content, sha256, page_count = extract_pdf_evidence(str(row["url"]))
        except Exception as exc:
            # A download failure is a source gap, not evidence against the rule.
            documents.append(
                {
                    "document_id": f"official_{len(documents) + 1}",
                    "title": row["title"],
                    "url": row["url"],
                    "published_at": row.get("published_at"),
                    "source": "巨潮资讯官方披露",
                    "content": "",
                    "read_error": str(exc),
                    "purpose": "只作为复核证据；不得修改主报告规则。",
                }
            )
            continue
        documents.append(
            {
                "document_id": f"official_{len(documents) + 1}",
                "title": row["title"],
                "url": row["url"],
                "published_at": row.get("published_at"),
                "source": "巨潮资讯官方披露",
                "sha256": sha256,
                "page_count": page_count,
                "content": content,
                "purpose": "只作为复核证据；不得修改主报告规则。",
            }
        )
    return documents


def collect_local_stock_evidence(
    repo_root: Path,
    resolution: dict[str, Any],
) -> list[dict[str, Any]]:
    """Collect one stock's local evidence without changing its locked rules."""
    report_path = repo_root / str(resolution.get("report_path") or "")
    if not report_path.is_file():
        raise RuntimeError(f"主报告不存在：{resolution.get('report_path')}")
    company_dir = report_path.parent
    task_text = " ".join(
        str(task.get(field) or "")
        for task in (resolution.get("judgment") or {}).get("review_tasks", [])
        for field in ("content", "metrics", "periods")
    )
    candidates = [report_path]
    for path in sorted(company_dir.rglob("*")):
        name = path.name.lower()
        if not path.is_file() or path == report_path:
            continue
        if any(token in name for token in ("checklist", "technical", "sentiment", "情绪", "技术面")):
            continue
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        # The main report is the fixed-rule reference.  Other local reports
        # and source notes are the preferred current evidence layer.
        if any(token in name for token in ("thesis", "tracker", "source", "复核", "跟踪")):
            candidates.append(path)
    documents: list[dict[str, Any]] = []
    for path in candidates[:6]:
        raw = path.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()
        if path == report_path:
            # Keep the report as a dated baseline/reference.  It is never
            # treated as permission to replace the structured rule package.
            selected = lines
            source_role = "main_report_reference"
        else:
            keywords = [token for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9%./+-]{2,}", task_text) if len(token) >= 2]
            matched = [
                f"L{index + 1}: {line}"
                for index, line in enumerate(lines)
                if any(keyword in line for keyword in keywords)
            ]
            selected = matched[:240] or [f"L{index + 1}: {line}" for index, line in enumerate(lines[:240])]
            source_role = "local_current_evidence"
        content = "\n".join(
            line if line.startswith("L") else f"L{index + 1}: {line}"
            for index, line in enumerate(selected)
        )[:18000]
        documents.append(
            {
                "document_id": f"local_{len(documents) + 1}",
                "path": str(path.relative_to(repo_root)),
                "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                "source_role": source_role,
                "content": content,
                "purpose": "只作为复核证据；不得修改主报告规则。",
            }
        )
    return documents


def review_locked_tasks_with_local_model(
    resolution: dict[str, Any],
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Review all fixed tasks from local evidence using a closed JSON protocol."""
    config = opportunity_review.model_config("scan_flash")
    judgment = resolution.get("judgment") or {}
    tasks = judgment.get("review_tasks") or []
    task_catalog = {
        str(task.get("task_id")): {
            "scope_label": task.get("scope_label"),
            "content": task.get("content"),
            "metrics": task.get("metrics") or [],
            "periods": task.get("periods") or [],
            "schedule_type": task.get("schedule_type"),
        }
        for task in tasks
        if task.get("task_id")
    }
    document_catalog = {
        document["document_id"]: {
            "path": document["path"],
            "source_role": document["source_role"],
            "content": document["content"],
        }
        for document in documents
    }
    system = (
        "你是股票主报告复核证据核验员。输入的 review_tasks 是已经人工锁定的规则，"
        "你无权新增、删除、修改、放宽或重解释任何任务、阈值、价格带或条件。"
        "只能依据 document_catalog 中的本地文档进行核验，不得使用外部知识。"
        "主报告 reference 只能作为报告中已写出的基线，不能伪装成新的独立验证。"
        "没有当前数值、对比期、事件确认或一手证据时，必须使用 data_insufficient。"
        "不得给投资、交易或仓位建议。必须严格输出 JSON。"
    )
    user = json.dumps(
        {
            "schema": {
                "task_results": [
                    {
                        "task_id": "必须与 task_catalog 的键一一对应",
                        "status": "only: verified/not_triggered/triggered/data_insufficient",
                        "evidence_document_ids": "only document_catalog keys, at most 3",
                        "evidence_lines": "at most 3 objects: document_id, line_ref, exact_quote",
                        "missing_codes": "only no_current_value/no_comparison/no_threshold/no_official_source/no_event_confirmation",
                    }
                ],
                "rule_update": "must be manual_only",
            },
            "task_catalog": task_catalog,
            "document_catalog": document_catalog,
            "rule_update_policy": "manual_only; local documents are evidence only",
        },
        ensure_ascii=False,
    )
    response, reasoning = opportunity_review.request_json(config, system=system, user=user)
    raw_results = response.get("task_results")
    if not isinstance(raw_results, list):
        raise RuntimeError("模型未返回 task_results 数组")
    by_id: dict[str, dict[str, Any]] = {}
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("task_id") or "")
        if task_id not in task_catalog or task_id in by_id:
            raise RuntimeError(f"模型返回了未知或重复的 task_id：{task_id!r}")
        status = str(item.get("status") or "")
        if status not in ALLOWED_TASK_REVIEW_STATUSES:
            raise RuntimeError(f"模型返回了无效任务状态：{status!r}")
        evidence_ids = [str(value) for value in (item.get("evidence_document_ids") or [])[:3]]
        if any(value not in document_catalog for value in evidence_ids):
            raise RuntimeError(f"模型引用了不存在的本地证据：{task_id}")
        missing_codes = [str(value) for value in (item.get("missing_codes") or [])[:5]]
        if any(value not in ALLOWED_TASK_MISSING_CODES for value in missing_codes):
            raise RuntimeError(f"模型返回了未定义的数据缺口：{task_id}")
        evidence_lines = []
        for line in (item.get("evidence_lines") or [])[:3]:
            if not isinstance(line, dict) or str(line.get("document_id") or "") not in evidence_ids:
                raise RuntimeError(f"模型返回了无效证据行：{task_id}")
            evidence_lines.append(
                {
                    "document_id": str(line["document_id"]),
                    "line_ref": str(line.get("line_ref") or ""),
                    "exact_quote": str(line.get("exact_quote") or ""),
                }
            )
        by_id[task_id] = {
            "task_id": task_id,
            "status": status,
            "evidence_document_ids": evidence_ids,
            "evidence_lines": evidence_lines,
            "missing_codes": missing_codes,
        }
    # A malformed or incomplete model response must not erase a stock's task.
    # Missing task results are explicit data gaps and remain independently saved.
    results = []
    for task_id in task_catalog:
        results.append(
            by_id.get(
                task_id,
                {
                    "task_id": task_id,
                    "status": "data_insufficient",
                    "evidence_document_ids": [],
                    "evidence_lines": [],
                    "missing_codes": ["no_current_value"],
                },
            )
        )
    return {
        "status": "completed",
        "rule_update": "manual_only",
        "tasks": results,
        "model": config.model,
        "reasoning": reasoning,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace one stock result, never partially write its JSON."""
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
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def full_local_result(
    repo_root: Path,
    resolution: dict[str, Any],
    documents: list[dict[str, Any]],
    model_result: dict[str, Any],
) -> dict[str, Any]:
    judgment = resolution.get("judgment") or {}
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "company": resolution.get("company"),
        "ticker": resolution.get("ticker"),
        "scope": "A股主报告固定任务的本地证据复核；不读取 Checklist、技术面、情绪面或旧人工执行复核。",
        "main_report": {
            "path": resolution.get("report_path"),
            "sha256": resolution.get("report_sha256"),
            "rule_update_mode": "manual_only",
            "automatic_rule_replacement": False,
            "manual_judgment_reviewed_at": resolution.get("reviewed_at"),
        },
        "fixed_tasks": judgment.get("review_tasks") or [],
        "local_evidence_documents": [
            {key: value for key, value in document.items() if key != "content"}
            for document in documents
        ],
        "model_review": model_result,
    }


def load_a_share_resolutions(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "data" / "investment-dashboard" / "main_report_resolutions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("resolutions") or []
    return [
        row for row in rows
        if str(row.get("ticker") or "").upper().endswith((".SH", ".SZ", ".BJ"))
        and isinstance(row.get("judgment"), dict)
        and isinstance(row["judgment"].get("review_tasks"), list)
    ]


def run_full_local(
    repo_root: Path,
    output_dir: Path,
    *,
    resume: bool = False,
    workers: int = 4,
) -> dict[str, int]:
    """Run all A-share stocks independently and atomically save each result."""
    resolutions = load_a_share_resolutions(repo_root)
    counts = {"total": len(resolutions), "completed": 0, "error": 0, "skipped": 0}
    pending: list[tuple[int, dict[str, Any], Path]] = []
    for index, resolution in enumerate(resolutions, start=1):
        ticker = str(resolution["ticker"])
        output_path = output_dir / f"{ticker}.json"
        if resume and output_path.is_file():
            try:
                existing = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if existing.get("status") != "error":
                counts["skipped"] += 1
                print(f"[{index}/{len(resolutions)}] {ticker} skipped (existing atomic result)", flush=True)
                continue
            print(f"[{index}/{len(resolutions)}] {ticker} retrying prior error", flush=True)
        pending.append((index, resolution, output_path))

    def process_one(
        entry: tuple[int, dict[str, Any], Path],
    ) -> tuple[int, str, Path, dict[str, Any] | None, str | None]:
        index, resolution, output_path = entry
        ticker = str(resolution["ticker"])
        try:
            documents = collect_local_stock_evidence(repo_root, resolution)
            model_result = review_locked_tasks_with_local_model(resolution, documents)
            payload = full_local_result(repo_root, resolution, documents, model_result)
            atomic_write_json(output_path, payload)
            return index, ticker, output_path, payload, None
        except Exception as exc:
            error_payload = {
                "schema_version": 1,
                "generated_at": now_iso(),
                "company": resolution.get("company"),
                "ticker": ticker,
                "status": "error",
                "error": str(exc),
                "main_report": {
                    "path": resolution.get("report_path"),
                    "sha256": resolution.get("report_sha256"),
                    "rule_update_mode": "manual_only",
                    "automatic_rule_replacement": False,
                },
            }
            atomic_write_json(output_path, error_payload)
            return index, ticker, output_path, error_payload, str(exc)
    if not pending:
        return counts
    worker_count = max(1, min(int(workers), len(pending)))
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="fundamental-review") as pool:
        futures = [pool.submit(process_one, entry) for entry in pending]
        for future in as_completed(futures):
            index, ticker, output_path, payload, error = future.result()
            if error is None:
                counts["completed"] += 1
                print(f"[{index}/{len(resolutions)}] {ticker} completed -> {output_path.name}", flush=True)
            else:
                counts["error"] += 1
                print(f"[{index}/{len(resolutions)}] {ticker} error: {error}", file=sys.stderr, flush=True)
    return counts


def consecutive_deducted_profit_yoy(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current_q1 = find_period(records, "2026一季报")
    previous_q1 = find_period(records, "2025一季报")
    current_h1 = find_period(records, "2026中报")
    previous_h1 = find_period(records, "2025中报")
    q2_current = (current_h1["deducted_profit"] or 0) - (current_q1["deducted_profit"] or 0)
    q2_previous = (previous_h1["deducted_profit"] or 0) - (previous_q1["deducted_profit"] or 0)
    q2_yoy = (q2_current / q2_previous - 1) * 100 if q2_previous else None
    return [
        {"period": "2026Q1", "value": current_q1["deducted_profit_yoy"]},
        {"period": "2026Q2", "value": q2_yoy},
    ]


def evaluate_rules(records: list[dict[str, Any]], quote: dict[str, Any]) -> list[dict[str, Any]]:
    h1 = find_period(records, "2026中报")
    q1 = find_period(records, "2026一季报")
    annual_2025 = find_period(records, "2025年报")
    annual_2024 = find_period(records, "2024年报")
    deducted_growth = consecutive_deducted_profit_yoy(records)
    growth_passes = [point for point in deducted_growth if (point["value"] or -999) > 15]
    cash_improved = (h1["operating_cash_flow"] or float("-inf")) > 0
    gross_margin_stable = all((point["gross_margin"] or -999) >= 32 for point in (q1, h1))
    annual_cash_conversion = [
        {"period": row["period"], "value": (row["operating_cash_flow"] or 0) / row["net_profit"] if row["net_profit"] else None}
        for row in (annual_2024, annual_2025)
    ]
    cash_redline = all((point["value"] or float("inf")) < 0.70 for point in annual_cash_conversion)
    price = quote["price"]
    return [
        {
            "rule_id": "positive_quality_upgrade",
            "category": "positive_condition",
            "status": "met" if len(growth_passes) >= 2 and cash_improved and gross_margin_stable else "not_met",
            "rule": "连续至少两季扣非归母净利润同比 >15%，经营现金流改善，且毛利率稳定在 32% 以上。",
            "source": "主报告 L366-L369；其中“连续 2-3 季”按最小两季测试，三季仅增强置信度。",
            "evidence": {
                "deducted_profit_yoy": deducted_growth,
                "operating_cash_flow_h1": h1["operating_cash_flow"],
                "gross_margin": [{"period": row["period"], "value": row["gross_margin"]} for row in (q1, h1)],
            },
        },
        {
            "rule_id": "margin_redline",
            "category": "redline",
            "status": "breached" if (h1["gross_margin"] or 100) < 30 else "not_breached",
            "rule": "综合毛利率跌破 30%。",
            "source": "主报告 L186、L368。",
            "evidence": {"period": h1["period"], "gross_margin": h1["gross_margin"]},
        },
        {
            "rule_id": "cash_conversion_redline",
            "category": "redline",
            "status": "breached" if cash_redline else "not_breached",
            "rule": "经营现金流连续两年低于归母净利润的 70%。",
            "source": "主报告 L368。仅以完整年报判定。",
            "evidence": {"annual_operating_cash_flow_over_net_profit": annual_cash_conversion},
        },
        {
            "rule_id": "high_price_without_quality",
            "category": "redline",
            "status": "not_applicable" if price is not None and price < 18 else "review_required",
            "rule": "股价 18 元以上但扣非增速没有提升。",
            "source": "主报告 L368。当前价格未达到价格前提时不评价利润条件。",
            "evidence": {"current_price": price, "price_threshold": 18},
        },
        {
            "rule_id": "low_margin_mix",
            "category": "semantic_redline",
            "status": "pending_model_review",
            "rule": "储能/工程低毛利业务占比快速上升。",
            "source": "主报告 L368。只允许根据最新中报分产品表判断，不创造“快速上升”的阈值。",
            "evidence": {},
        },
        {
            "rule_id": "overseas_and_vpp_orders",
            "category": "event_condition",
            "status": "data_unavailable",
            "rule": "以海外/虚拟电厂订单和国外收入回款验证第二曲线质量。",
            "source": "主报告 L366、L369。主报告未给出可自动判定的阈值，不能将新闻或普通营收替代为订单与回款。",
            "evidence": {
                "required_sources": ["公司中标/订单公告", "定期报告的海外应收或回款披露", "虚拟电厂项目利润率披露"],
            },
        },
    ]


def comparison_rows(records: list[dict[str, Any]], quote: dict[str, Any]) -> list[dict[str, Any]]:
    h1 = find_period(records, "2026中报")
    h1_previous = find_period(records, "2025中报")
    q1 = find_period(records, "2026一季报")
    annual_2025 = find_period(records, "2025年报")
    annual_2024 = find_period(records, "2024年报")
    q_growth = consecutive_deducted_profit_yoy(records)
    cash_ratio_2025 = (annual_2025["operating_cash_flow"] or 0) / annual_2025["net_profit"]
    cash_ratio_2024 = (annual_2024["operating_cash_flow"] or 0) / annual_2024["net_profit"]
    return [
        {
            "metric": "扣非归母净利润同比",
            "current": q_growth,
            "comparison": "连续两季均未达到报告所列的正向验证线。",
            "threshold": "连续至少两季 >15%",
            "status": "not_met",
        },
        {
            "metric": "综合毛利率",
            "current": {"period": h1["period"], "value": h1["gross_margin"]},
            "comparison": {"Q1": q1["gross_margin"], "上年同期": h1_previous["gross_margin"], "同比百分点": (h1["gross_margin"] or 0) - (h1_previous["gross_margin"] or 0)},
            "threshold": "目标 ≥32%；红线 <30%",
            "status": "warning",
        },
        {
            "metric": "经营现金流净额",
            "current": {"period": h1["period"], "value": h1["operating_cash_flow"]},
            "comparison": {"上年同期": h1_previous["operating_cash_flow"], "同比变化": (h1["operating_cash_flow"] or 0) - (h1_previous["operating_cash_flow"] or 0)},
            "threshold": "报告要求改善；年度红线见现金转化率",
            "status": "warning",
        },
        {
            "metric": "经营现金流/归母净利润",
            "current": {"period": annual_2025["period"], "value": cash_ratio_2025},
            "comparison": {"2024年报": cash_ratio_2024},
            "threshold": "连续两年 <0.70 才触发红线",
            "status": "not_breached",
        },
        {
            "metric": "价格质量红线前提",
            "current": quote["price"],
            "comparison": "当前价格未进入高估值价格前提。",
            "threshold": "价格 ≥18 元后才复核扣非增速是否改善",
            "status": "not_applicable",
        },
    ]


def semantic_review(segment_rows: list[dict[str, Any]], rule: dict[str, Any]) -> dict[str, Any]:
    config = opportunity_review.model_config("scan_flash")
    evidence_catalog = {
        f"segment_{index + 1}": row
        for index, row in enumerate(segment_rows)
    }
    system = (
        "你是上市公司基本面条件核验员。只判断输入中这一条主报告红线是否已有明确证据，"
        "不得给投资、交易、仓位或价格建议；不得自行发明阈值；不得引用输入以外事实。"
        "不要输出自然语言摘要或数字；只能用 evidence_ids 选择输入目录中的证据。"
        "如果 coverage_gap 表明该红线的任何一个组成业务没有单独披露，必须输出 inconclusive，不能以其他组成业务的证据替代。"
        "输出严格 JSON 对象。"
    )
    user = json.dumps(
        {
            "schema": {
                "status": "only: not_breached/warning/breached/inconclusive",
                "evidence_ids": ["只可选 evidence_catalog 的键，最多3条"],
                "missing_evidence_codes": ["only: no_segment_share_history/no_engineering_revenue/no_order_or_backlog_detail"],
            },
            "rule": rule,
            "evidence_catalog": evidence_catalog,
            "coverage_gap": "官方中报没有单列工程业务收入、毛利率或占比；只能直接核验储能业务。",
        },
        ensure_ascii=False,
    )
    response, reasoning = opportunity_review.request_json(config, system=system, user=user)
    state = str(response.get("status") or "").strip()
    if state not in ALLOWED_SEMANTIC_STATES:
        raise RuntimeError(f"模型返回了无效复核状态：{state!r}")
    evidence_ids = [str(item) for item in response.get("evidence_ids", [])[:3]]
    if any(item not in evidence_catalog for item in evidence_ids):
        raise RuntimeError("模型引用了不存在的证据编号")
    missing_codes = [str(item) for item in response.get("missing_evidence_codes", [])[:2]]
    allowed_missing = {"no_segment_share_history", "no_engineering_revenue", "no_order_or_backlog_detail"}
    if any(item not in allowed_missing for item in missing_codes):
        raise RuntimeError("模型返回了未定义的数据缺口代码")
    summaries = {
        "not_breached": "已列证据未显示报告指定的低毛利储能或工程业务占比快速上升。",
        "warning": "已有需要继续跟踪的业务结构变化，但证据不足以确认主报告红线。",
        "breached": "已列证据支持主报告的低毛利业务结构红线被触发。",
        "inconclusive": "现有分产品披露不足以判断该主报告红线。",
    }
    return {
        "status": state,
        "summary": summaries[state],
        "evidence": [
            {"evidence_id": item, "source": "巨潮 2026H1 分产品表", **evidence_catalog[item]}
            for item in evidence_ids
        ],
        "missing_evidence_codes": missing_codes,
        "model": config.model,
        "reasoning": reasoning,
    }


def review_fixed_rule_evidence(
    rule: dict[str, Any],
    documents: list[dict[str, Any]],
    *,
    evidence_layer: str,
) -> dict[str, Any]:
    """Let the model read evidence without granting it main-report rule authority."""
    config = opportunity_review.model_config("scan_flash")
    document_catalog = {
        document["document_id"]: {
            "path": document.get("path"),
            "title": document.get("title"),
            "url": document.get("url"),
            "content": document["content"],
        }
        for document in documents
    }
    system = (
        "你是上市公司复核证据整理员。主报告规则已经人工锁定；你无权新增、删除、"
        "调整或重解释任何红线、阈值、价格带或条件。只从输入的本地资料判断："
        "是否已经存在该既有复核事项的证据。不得给投资、交易、仓位或价格建议，不得使用输入以外事实。"
        "只输出严格 JSON，不写自然语言结论。"
    )
    user = json.dumps(
        {
            "schema": {
                "availability": "only: verified/partial/not_disclosed",
                "evidence_document_ids": ["only keys from document_catalog, at most 3"],
                "missing_codes": ["only: current_order_amount/overseas_collection/vpp_project_margin"],
                "candidate_risk": "only: none/new_risk_candidate",
            },
            "fixed_rule": rule,
            "document_catalog": document_catalog,
            "rule_change_policy": "manual_only; current documents are read-only evidence, never a rule update",
        },
        ensure_ascii=False,
    )
    response, reasoning = opportunity_review.request_json(config, system=system, user=user)
    availability = str(response.get("availability") or "").strip()
    if availability not in ALLOWED_LOCAL_EVIDENCE_AVAILABILITY:
        raise RuntimeError(f"模型返回了无效本地证据状态：{availability!r}")
    evidence_ids = [str(item) for item in response.get("evidence_document_ids", [])[:3]]
    if any(item not in document_catalog for item in evidence_ids):
        raise RuntimeError("模型引用了不存在的本地证据文件")
    missing_codes = [str(item) for item in response.get("missing_codes", [])[:3]]
    allowed_missing = {"current_order_amount", "overseas_collection", "vpp_project_margin"}
    if any(item not in allowed_missing for item in missing_codes):
        raise RuntimeError("模型返回了未定义的本地证据缺口")
    candidate_risk = str(response.get("candidate_risk") or "").strip()
    if candidate_risk not in {"none", "new_risk_candidate"}:
        raise RuntimeError("模型返回了未定义的候选风险状态")
    summaries = {
        "verified": "本地最新资料已覆盖该复核事项所需证据。",
        "partial": "本地最新资料有部分验证事实，但不足以覆盖既有复核事项的全部口径。",
        "not_disclosed": "已读取的本地最新资料未披露该复核事项所需事实。",
    }
    return {
        "evidence_layer": evidence_layer,
        "availability": availability,
        "summary": summaries[availability],
        "evidence_documents": [
            {
                "document_id": item,
                "path": document_catalog[item].get("path"),
                "title": document_catalog[item].get("title"),
                "url": document_catalog[item].get("url"),
            }
            for item in evidence_ids
        ],
        "missing_codes": missing_codes,
        "candidate_risk": candidate_risk,
        "model": config.model,
        "reasoning": reasoning,
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# 东方电子主报告复核雷达（本地试点）",
        "",
        f"生成时间：{result['generated_at']}",
        "",
        "规则版本：人工锁定；本次模型只读取更新资料作为证据，不能改动红线。",
        "",
        "## 数值对比",
        "",
        "| 指标 | 当前 | 对比 | 阈值/规则 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for row in result["comparisons"]:
        current, comparison = readable_comparison(row)
        lines.append(f"| {row['metric']} | {current} | {comparison} | {row['threshold']} | {row['status']} |")
    lines.extend(["", "## 模型读取的最新本地资料", ""])
    for document in result["local_evidence_documents"]:
        lines.append(f"- {document['document_id']}：{document['path']}（SHA-256：{document['sha256'][:12]}…）")
    lines.extend(["", "## 补证用的近期官方公告", ""])
    if not result["official_evidence_documents"]:
        lines.append("- 巨潮近期公告中没有匹配到可读取的相关披露；这不是‘已复核’。")
    for document in result["official_evidence_documents"]:
        status = f"读取失败：{document['read_error']}" if document.get("read_error") else f"SHA-256：{document['sha256'][:12]}…"
        lines.append(f"- {document['document_id']}：{document['published_at'] or '日期未知'} {document['title']}（{status}）")
    lines.extend(["", "## 条件型事项的证据结论", ""])
    for rule in result["rules"]:
        if rule.get("category") != "event_condition":
            continue
        evidence = rule.get("evidence") or {}
        lines.append(f"- **{rule['rule_id']}**：{evidence.get('availability', '未运行')}（{evidence.get('summary', '')}）")
        if evidence.get("missing_codes"):
            lines.append(f"  - 仍缺：{'、'.join(evidence['missing_codes'])}")
    lines.extend(["", "## 规则状态", ""])
    for rule in result["rules"]:
        lines.append(f"- **{rule['rule_id']}**：{rule['status']} — {rule['rule']}")
    return "\n".join(lines) + "\n"


def readable_comparison(row: dict[str, Any]) -> tuple[str, str]:
    """Keep the pilot's human-facing comparison table compact and legible."""
    metric = row["metric"]
    if metric == "扣非归母净利润同比":
        values = "；".join(f"{item['period']} {item['value']:+.2f}%" for item in row["current"])
        return values, str(row["comparison"])
    if metric == "综合毛利率":
        current = f"{row['current']['period']} {row['current']['value']:.2f}%"
        prior = row["comparison"]
        return current, f"Q1 {prior['Q1']:.2f}%；上年同期 {prior['上年同期']:.2f}%；同比 {prior['同比百分点']:+.2f}pct"
    if metric == "经营现金流净额":
        current = f"{row['current']['period']} {row['current']['value'] / 1e8:.2f}亿元"
        prior = row["comparison"]
        return current, f"上年同期 {prior['上年同期'] / 1e8:.2f}亿元；同比 {prior['同比变化'] / 1e8:+.2f}亿元"
    if metric == "经营现金流/归母净利润":
        current = f"{row['current']['period']} {row['current']['value']:.2f}x"
        return current, f"2024年报 {row['comparison']['2024年报']:.2f}x"
    if metric == "价格质量红线前提":
        return f"{row['current']:.2f}元", str(row["comparison"])
    return str(row["current"]), str(row["comparison"])


def build_result(ticker: str, *, with_model: bool, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or Path.cwd()
    records = [normalise_financial_record(row) for row in fetch_eastmoney_financials(ticker)]
    cninfo, cninfo_meta = extract_cninfo_h1(CNINFO_H1_URL)
    h1 = find_period(records, "2026中报")
    quote = fetch_quote(ticker)
    comparisons = {}
    for key in ("revenue", "net_profit", "deducted_profit", "operating_cash_flow"):
        comparisons[key] = {
            "eastmoney": h1[key],
            "cninfo": cninfo[key],
            "error_pct": percentage_error(h1[key], cninfo[key]),
            "verified": (percentage_error(h1[key], cninfo[key]) or 0) <= 1,
        }
    rules = evaluate_rules(records, quote)
    local_documents = collect_latest_local_evidence(repo_root)
    official_documents: list[dict[str, Any]] = []
    semantic = next(rule for rule in rules if rule["rule_id"] == "low_margin_mix")
    orders = next(rule for rule in rules if rule["rule_id"] == "overseas_and_vpp_orders")
    if with_model:
        model_result = semantic_review(cninfo_meta["segments"], semantic)
        semantic["status"] = model_result["status"]
        semantic["evidence"] = model_result
        local_model_result = review_fixed_rule_evidence(
            orders, local_documents, evidence_layer="local_latest_documents"
        )
        evidence_result = local_model_result
        # Local material is preferred.  Only when it cannot cover the locked
        # condition do we fetch current first-party disclosures as a second
        # layer; neither layer receives authority to change the rule package.
        if local_model_result["availability"] != "verified":
            official_documents = collect_recent_official_evidence(ticker)
            readable_official_documents = [
                document for document in official_documents if document.get("content")
            ]
            if readable_official_documents:
                official_model_result = review_fixed_rule_evidence(
                    orders,
                    readable_official_documents,
                    evidence_layer="recent_cninfo_official_disclosures",
                )
                evidence_result = {
                    **official_model_result,
                    "local_first_result": local_model_result,
                }
            else:
                evidence_result = {
                    **local_model_result,
                    "official_evidence_status": "no_readable_recent_official_disclosure",
                }
        orders["status"] = "not_breached" if evidence_result["availability"] == "verified" else "inconclusive"
        orders["evidence"] = evidence_result
    else:
        semantic["status"] = "inconclusive"
        semantic["evidence"] = {"note": "本次未调用模型；只完成数值规则验证。"}
        orders["status"] = "inconclusive"
        orders["evidence"] = {"note": "本次未调用模型；未读取本地更新资料或官方补证。"}
    breached = [rule["rule_id"] for rule in rules if rule["status"] == "breached"]
    warning = [rule["rule_id"] for rule in rules if rule["status"] == "warning"]
    unmet_positive = [rule["rule_id"] for rule in rules if rule["category"] == "positive_condition" and rule["status"] == "not_met"]
    unresolved = [rule["rule_id"] for rule in rules if rule["status"] in {"inconclusive", "data_unavailable", "review_required"}]
    return {
        "schema_version": 2,
        "pilot": True,
        "generated_at": now_iso(),
        "company": "东方电子",
        "ticker": ticker,
        "scope": "主报告明确条件的单股本地验证；不读取 Checklist、技术面、情绪面或旧人工执行复核。模型可读取更新的本地基本面资料作为证据，但无权变更规则。",
        "main_report": {
            "path": "reports/东方电子/东方电子投资研究报告-20260707.md",
            "sha256": hashlib.sha256((repo_root / "reports/东方电子/东方电子投资研究报告-20260707.md").read_bytes()).hexdigest(),
            "rule_update_mode": "manual_only",
            "automatic_rule_replacement": False,
        },
        "sources": {
            "eastmoney_financials": {"report_date": h1["report_date"], "source": EASTMONEY_URL},
            "cninfo_official_filing": cninfo_meta,
            "quote": quote,
            "cross_check": comparisons,
        },
        "local_evidence_documents": [
            {key: value for key, value in document.items() if key != "content"}
            for document in local_documents
        ],
        "official_evidence_documents": [
            {key: value for key, value in document.items() if key != "content"}
            for document in official_documents
        ],
        "comparisons": comparison_rows(records, quote),
        "rules": rules,
        "summary": {
            "overall_status": "redline_breached" if breached else "needs_fundamental_attention" if warning or unmet_positive or unresolved else "no_confirmed_redline",
            "breached_rule_ids": breached,
            "warning_rule_ids": warning,
            "unmet_positive_rule_ids": unmet_positive,
            "unresolved_rule_ids": unresolved,
            "next_evidence": "2026年三季报后重新检查扣非增速、毛利率、经营现金流与分产品结构。",
            "decision_boundary": "本结果仅升级独立复核状态，不修改主报告判断、人工价格分区或现有可执行分区。",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="单股票主报告基本面复核雷达")
    parser.add_argument("--ticker", default="000682.SZ")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path, help="写入可读的本地对比结果")
    parser.add_argument("--skip-model", action="store_true", help="只验证可计算规则，不调用 OpenCode")
    parser.add_argument("--all-a-shares", action="store_true", help="按主报告裁决逐只运行 93 只 A 股本地复核")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("local/fundamental-review-full"),
        help="全量模式的逐股票原子结果目录",
    )
    parser.add_argument("--resume", action="store_true", help="全量模式跳过已有逐股票结果")
    parser.add_argument("--workers", type=int, default=4, help="全量模式最大并发 OpenCode 请求数，默认 4")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.all_a_shares:
        if args.skip_model:
            raise SystemExit("全量本地复核必须调用 OpenCode 模型；不能与 --skip-model 同时使用。")
        counts = run_full_local(args.repo_root.resolve(), args.output_dir, resume=args.resume, workers=args.workers)
        print(json.dumps(counts, ensure_ascii=False, indent=2))
        return
    if args.output is None:
        parser.error("单股模式必须提供 --output；全量模式请使用 --all-a-shares")
    if args.ticker != "000682.SZ":
        raise SystemExit("本地首个试点仅配置东方电子（000682.SZ）。")
    result = build_result(args.ticker, with_model=not args.skip_model, repo_root=args.repo_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
