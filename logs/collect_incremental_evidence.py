# 一次性执行记录：为增量复核采集全部 93 只的证据包（本地新资料 + 巨潮官方公告 PDF）。
# 证据采集与指纹全部调用 tools/main_report_review.py 原生函数；单只失败不影响其他股票。
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, "tools")
import main_report_review as mrr

root = Path(".").resolve()
rules_dir = root / "data/investment-dashboard/main-report-review-rules"
out_dir = root / "local/main-report-review-evidence"
out_dir.mkdir(parents=True, exist_ok=True)
packages = mrr.load_rule_packages(rules_dir)
only = {a.upper() for a in sys.argv[1:]}
if only:
    packages = [p for p in packages if str(p.get("ticker")) in only]
print_counter = {"done": 0}
lock = threading.Lock()

CURRENT_ROLES = {"local_current_evidence", "zcode_current_evidence_extract", "official_current_evidence"}


def classify(package, documents):
    if package.get("rule_state") != "active":
        return "stale"
    if not any(rule.get("reviewable") is True for rule in package.get("active_rules") or []):
        return "no_rules"
    if not any(d.get("source_role") in CURRENT_ROLES for d in documents):
        return "waiting"
    return "due"


def collect(package):
    ticker = str(package.get("ticker") or "")
    documents = mrr.collect_local_evidence(root, package)
    official_error = None
    try:
        documents.extend(mrr.collect_official_evidence(package))
    except Exception as exc:
        official_error = str(exc)
    packet = {
        "ticker": ticker,
        "company": package.get("company"),
        "rule_state": package.get("rule_state"),
        "rules_fingerprint": package.get("rules_fingerprint"),
        "main_report": package.get("main_report"),
        "active_rules": package.get("active_rules"),
        "pending_redline_candidates": len(package.get("audit_candidates") or []),
        "documents": documents,
        "official_fetch_error": official_error,
        "classification": classify(package, documents),
    }
    mrr.atomic_write_json(out_dir / f"{ticker}.json", packet)
    with lock:
        print_counter["done"] += 1
        n = print_counter["done"]
    roles = [d.get("source_role") for d in documents]
    print(
        f"[{n}/{len(packages)}] {ticker} {packet['classification']} "
        f"docs={len(documents)} official={roles.count('official_current_evidence')} "
        f"local_current={roles.count('local_current_evidence')} "
        f"zcode_extract={roles.count('zcode_current_evidence_extract')}"
        + (f" official_error={official_error}" if official_error else ""),
        flush=True,
    )
    return ticker


with ThreadPoolExecutor(max_workers=4, thread_name_prefix="evidence-collect") as pool:
    futures = [pool.submit(collect, package) for package in packages]
    done = 0
    for future in as_completed(futures):
        try:
            future.result()
            done += 1
        except Exception as exc:
            print(f"collection-failure: {exc}", file=sys.stderr, flush=True)
print(f"DONE {done}/{len(packages)}", flush=True)
