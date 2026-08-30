# 一次性执行记录：为 ZCode 独立规则复核生成 93 只股票的工作清单。
# 仅收集报告与本地证据文档的路径映射，不读取人工锁定规则内容。
import sys, json
sys.path.insert(0, "tools")
from pathlib import Path
import fundamental_review_radar as radar

root = Path(".").resolve()
resolutions = radar.load_a_share_resolutions(root)
manifest = []
for res in resolutions:
    ticker = str(res["ticker"])
    report_path = root / str(res.get("report_path") or "")
    if not report_path.is_file():
        manifest.append({"ticker": ticker, "company": res.get("company"),
                         "error": "report_missing", "report_path": str(res.get("report_path"))})
        continue
    company_dir = report_path.parent
    docs = [{"id": "local_1", "path": report_path.relative_to(root).as_posix(),
             "role": "main_report_reference"}]
    for path in sorted(company_dir.rglob("*")):
        name = path.name.lower()
        if not path.is_file() or path == report_path:
            continue
        if any(t in name for t in ("checklist", "technical", "sentiment", "情绪", "技术面")):
            continue
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        if any(t in name for t in ("thesis", "tracker", "source", "复核", "跟踪")):
            docs.append({"id": f"local_{len(docs)+1}",
                         "path": path.relative_to(root).as_posix(),
                         "role": "local_current_evidence"})
        if len(docs) >= 6:
            break
    manifest.append({"ticker": ticker, "company": res.get("company"),
                     "report_path": docs[0]["path"], "docs": docs})

out = Path("logs/zcode_review_manifest.json")
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
errs = [m for m in manifest if "error" in m]
doc_counts = [len(m["docs"]) for m in manifest if "error" not in m]
print("股票数:", len(manifest), "| 报告缺失:", len(errs), [e["ticker"] for e in errs])
dist = {n: doc_counts.count(n) for n in sorted(set(doc_counts))}
print("每只证据文档数分布:", dist)
