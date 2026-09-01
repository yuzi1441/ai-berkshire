# 一次性执行记录：从证据包构建子代理核验输入（紧凑版）。
# 主报告内容不进入代理目录（基线不可用于判定）；其余文档按规则关键词过滤行，
# 保留原文行号前缀，代理引用的 exact_quote 必须能在证据包全文中逐字命中。
import json
import re
from pathlib import Path

root = Path(".").resolve()
import sys
sys.path.insert(0, "tools")
import main_report_review as mrr

evidence_dir = root / "local/main-report-review-evidence"
out_dir = root / "local/main-report-review-agent-packets"
out_dir.mkdir(parents=True, exist_ok=True)

for packet_path in sorted(evidence_dir.glob("*.json")):
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("classification") != "due":
        continue
    ticker = packet["ticker"]
    task_catalog = {}
    for rule in packet.get("active_rules") or []:
        if rule.get("reviewable") is not True or rule.get("state") != "active":
            continue
        task_catalog[rule["rule_id"]] = {
            key: rule.get(key)
            for key in ("group", "polarity", "condition", "relation", "metrics",
                        "operator", "threshold", "periods", "evidence_requirement")
        }
    condition_text = " ".join(v["condition"] + " " + " ".join(v.get("metrics") or []) for v in task_catalog.values())
    keywords = [t for t in re.findall(r"[\u4e00-\u9fffA-Za-z0-9%./+-]{2,}", condition_text) if len(t) >= 2]
    document_catalog = {}
    for doc in packet.get("documents") or []:
        role = str(doc.get("source_role") or "")
        if role == "main_report_reference":
            continue
        full_lines = str(doc.get("content") or "").splitlines()
        if role in {"local_supporting_evidence"}:
            kept = [line for line in full_lines if any(k in line for k in keywords)][:60]
            if not kept:
                kept = full_lines[:40]
        else:
            kept = [line for line in full_lines if any(k in line for k in keywords)]
            if len(kept) < 25:
                kept = (kept + [line for line in full_lines if not any(k in line for k in keywords)])
            kept = kept[:150]
        document_catalog[doc["document_id"]] = {
            "path": doc.get("path"),
            "source_role": role,
            "document_date": doc.get("document_date"),
            "title": doc.get("title"),
            "content": "\n".join(kept)[:9000],
        }
    payload = {
        "ticker": ticker,
        "company": packet.get("company"),
        "task_catalog": task_catalog,
        "document_catalog": document_catalog,
    }
    mrr.atomic_write_json(out_dir / f"{ticker}.json", payload)

files = sorted(out_dir.glob("*.json"))
sizes = [(p.stat().st_size) for p in files]
print(f"代理包: {len(files)} 只 | 单包最小 {min(sizes)//1024}KB 最大 {max(sizes)//1024}KB 总计 {sum(sizes)//1024//1024}MB")
