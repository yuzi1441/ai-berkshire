# 一次性执行记录：组装增量复核结果（复刻引擎 review_rules_with_model 的 fail-closed 校验）。
# 结果经 tools/main_report_review.result_payload + atomic_write_json 原子写入，不覆盖旧结果目录语义：
# local/fundamental-review-current/ 只存"当前最新"，历史留档在 fundamental-review-full 与本批指纹字段中。
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "tools")
import main_report_review as mrr

root = Path(".").resolve()
rules_dir = root / "data/investment-dashboard/main-report-review-rules"
evidence_dir = root / "local/main-report-review-evidence"
agent_dir = root / "local/main-report-review-agent"
legacy_dir = root / "local/fundamental-review-full"
output_dir = root / "local/fundamental-review-current"
output_dir.mkdir(parents=True, exist_ok=True)

CURRENT_ROLES = {"local_current_evidence", "zcode_current_evidence_extract", "official_current_evidence"}
STATUS_MESSAGE = {
    "stale_rules": "主报告内容已变化，旧规则只读留档，等待人工重建",
    "no_rules": "当前只有价格规则，由人工复核价格分区处理",
    "waiting_evidence": "没有主报告基线之后的新证据，本次不调用模型",
}
MODEL_LABEL = "zcode-subagent-review/GLM（Windows 端 ZCode 子代理替代 OpenCode，协议 main-report-review-v2.2）"

packages = {str(p["ticker"]): p for p in mrr.load_rule_packages(rules_dir)}
legacy_status = {}
for path in sorted(legacy_dir.glob("*.json")):
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        summary = row.get("summary") or {}
        if summary.get("overall_status"):
            legacy_status[str(row.get("ticker"))] = summary.get("overall_status")
    except (OSError, json.JSONDecodeError):
        continue

counts = Counter()
redlines, changed, still_missing, new_evidence_stocks, agent_failures = [], [], [], [], []
official_doc_total = 0
for packet_path in sorted(evidence_dir.glob("*.json")):
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    ticker = packet["ticker"]
    package = packages.get(ticker)
    if package is None:
        continue
    documents = packet.get("documents") or []
    official_doc_total += sum(1 for d in documents if d.get("source_role") == "official_current_evidence")
    cls = packet.get("classification")
    if cls in {"stale", "no_rules", "waiting"}:
        payload = mrr.result_payload(package, documents, None,
                                     status={"stale": "stale_rules", "no_rules": "no_rules", "waiting": "waiting_evidence"}[cls],
                                     message=STATUS_MESSAGE[{"stale": "stale_rules", "no_rules": "no_rules", "waiting": "waiting_evidence"}[cls]])
        mrr.atomic_write_json(output_dir / f"{ticker}.json", payload)
        counts[{"stale": "stale", "no_rules": "no_rules", "waiting": "waiting"}[cls]] += 1
        continue
    task_catalog = {
        rule["rule_id"]: rule
        for rule in package.get("active_rules") or []
        if rule.get("state") == "active" and rule.get("reviewable") is True
    }
    document_roles = {str(d.get("document_id")): str(d.get("source_role") or "") for d in documents}
    agent_path = agent_dir / f"{ticker}.json"
    if not agent_path.is_file():
        agent_failures.append({"ticker": ticker, "error": "missing agent output"})
        payload = mrr.result_payload(package, documents, None, status="error", message="缺少子代理核验输出")
        mrr.atomic_write_json(output_dir / f"{ticker}.json", payload)
        counts["error"] += 1
        continue
    agent = json.loads(agent_path.read_text(encoding="utf-8"))
    by_id = {}
    broken = False
    for raw in agent.get("rule_results") or []:
        rule_id = str(raw.get("rule_id") or "")
        if rule_id not in task_catalog or rule_id in by_id:
            broken = True
            break
        truth_state = str(raw.get("truth_state") or "")
        if truth_state not in mrr.TRUTH_STATES:
            broken = True
            break
        evidence_ids = [str(v) for v in (raw.get("evidence_document_ids") or [])[:3]]
        if any(v not in document_roles for v in evidence_ids):
            broken = True
            break
        missing_codes = [str(v) for v in (raw.get("missing_codes") or [])[:5]]
        if any(v not in mrr.MISSING_CODES for v in missing_codes):
            broken = True
            break
        evidence_lines = []
        for line in (raw.get("evidence_lines") or [])[:3]:
            if not isinstance(line, dict) or str(line.get("document_id") or "") not in evidence_ids:
                broken = True
                break
            evidence_lines.append({
                "document_id": str(line["document_id"]),
                "line_ref": str(line.get("line_ref") or ""),
                "exact_quote": str(line.get("exact_quote") or ""),
            })
        if broken:
            break
        current_ids = [v for v in evidence_ids if document_roles.get(v) in CURRENT_ROLES]
        if truth_state in {"met", "not_met"} and (not current_ids or not evidence_lines):
            truth_state = "unknown"
            evidence_ids = current_ids
            evidence_lines = [line for line in evidence_lines if line["document_id"] in current_ids]
            if "no_current_value" not in missing_codes:
                missing_codes.append("no_current_value")
        rule = task_catalog[rule_id]
        requirements = set(rule.get("evidence_requirement") or [])
        if "current_value" in requirements and not mrr.compact_text(raw.get("current_value")) and "no_current_value" not in missing_codes:
            missing_codes.append("no_current_value")
        if "comparison" in requirements and not mrr.compact_text(raw.get("comparison")) and "no_comparison" not in missing_codes:
            missing_codes.append("no_comparison")
        if "official_source" in requirements and not any(document_roles.get(v) == "official_current_evidence" for v in current_ids) and "no_official_source" not in missing_codes:
            missing_codes.append("no_official_source")
        if "event_confirmation" in requirements and not evidence_lines and "no_event_confirmation" not in missing_codes:
            missing_codes.append("no_event_confirmation")
        if truth_state in {"met", "not_met"} and missing_codes:
            truth_state = "unknown"
        by_id[rule_id] = {
            "rule_id": rule_id,
            "truth_state": truth_state,
            "review_effect": mrr.effect_for_rule(rule, truth_state),
            "current_value": mrr.compact_text(raw.get("current_value")),
            "comparison": mrr.compact_text(raw.get("comparison")),
            "evidence_document_ids": evidence_ids,
            "evidence_lines": evidence_lines,
            "missing_codes": missing_codes,
        }
    if broken:
        agent_failures.append({"ticker": ticker, "error": "malformed agent output"})
        payload = mrr.result_payload(package, documents, None, status="error", message="子代理输出未通过协议校验")
        mrr.atomic_write_json(output_dir / f"{ticker}.json", payload)
        counts["error"] += 1
        continue
    results = []
    for rule_id, rule in task_catalog.items():
        results.append(by_id.get(rule_id, {
            "rule_id": rule_id,
            "truth_state": "unknown",
            "review_effect": "neutral",
            "current_value": "",
            "comparison": "",
            "evidence_document_ids": [],
            "evidence_lines": [],
            "missing_codes": ["no_current_value"],
        }))
    model_review = {
        "status": "completed",
        "rule_update": "manual_only",
        "model": MODEL_LABEL,
        "reasoning": "按 main-report-review-v2.2 封闭协议核验人工锁定规则的原子子句；仅 current 角色证据可判 met/not_met，缺口一律 unknown 并标注 missing_codes。",
        "rules": results,
        "new_observations": [
            {"text": mrr.compact_text(o.get("text")), "evidence_document_ids": [str(v) for v in (o.get("evidence_document_ids") or []) if str(v) in document_roles]}
            for o in (agent.get("new_observations") or []) if isinstance(o, dict) and mrr.compact_text(o.get("text"))
        ][:8],
    }
    payload = mrr.result_payload(package, documents, model_review)
    mrr.atomic_write_json(output_dir / f"{ticker}.json", payload)
    counts["completed"] += 1
    summary = payload.get("summary") or {}
    if summary.get("status") == "redline":
        redlines.append({"ticker": ticker, "company": payload.get("company"), "rule_ids": summary.get("redline_rule_ids")})
    if payload.get("current_evidence_count"):
        new_evidence_stocks.append({"ticker": ticker, "current_evidence_count": payload.get("current_evidence_count"),
                                    "latest_evidence_date": payload.get("latest_evidence_date")})
    if summary.get("status") == "data_gap" or summary.get("unknown_count"):
        still_missing.append({"ticker": ticker, "company": payload.get("company"),
                              "unknown_count": summary.get("unknown_count"),
                              "missing_requirements": summary.get("missing_requirements")})
    legacy = legacy_status.get(ticker)
    mapped = {"redline_breached": "redline", "needs_fundamental_attention": "attention", "no_confirmed_redline": "clear"}.get(legacy)
    if mapped and mapped != summary.get("status"):
        changed.append({"ticker": ticker, "company": payload.get("company"),
                        "legacy_status": legacy, "new_status": summary.get("status")})

summary = {
    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "counts": dict(counts),
    "status_distribution": {},
    "redline_stocks": redlines,
    "result_changes_vs_legacy": changed,
    "still_missing_data": still_missing,
    "stocks_with_new_evidence": len(new_evidence_stocks),
    "official_documents_downloaded": official_doc_total,
    "agent_failures": agent_failures,
}
final_statuses = Counter()
for path in sorted(output_dir.glob("*.json")):
    row = json.loads(path.read_text(encoding="utf-8"))
    final_statuses[(row.get("summary") or {}).get("status")] += 1
summary["status_distribution"] = dict(final_statuses)
mrr.atomic_write_json(output_dir / "增量重跑汇总-20260830.json", summary)
print(json.dumps(summary, ensure_ascii=False, indent=1)[:4000])
