# 一次性执行记录：校验 93 份 ZCode 独立规则复核输出，并组装为标准结果文件。
# 校验项：任务结构、状态/缺口枚举、证据文档 id 归属、引文与源文件行号逐字比对。
import sys, json, hashlib
from datetime import datetime
from pathlib import Path

root = Path(".").resolve()
manifest = json.loads((root / "logs/zcode_review_manifest.json").read_text(encoding="utf-8"))
out_dir = root / "local/fundamental-review-zcode/agent_out"
final_dir = root / "local/fundamental-review-zcode/full-zcode-rules"
final_dir.mkdir(parents=True, exist_ok=True)

STATUSES = {"verified", "not_triggered", "triggered", "data_insufficient"}
MISSING = {"no_current_value", "no_comparison", "no_threshold", "no_official_source", "no_event_confirmation"}
TASK_IDS = {"entry", "holder", "risk"}


def atomic_write_json(path: Path, payload: dict) -> None:
    import os, tempfile
    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                      prefix=f".{path.name}.", suffix=".tmp", delete=False)
    try:
        with tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
        os.replace(Path(tmp.name), path)
    finally:
        if Path(tmp.name).exists():
            Path(tmp.name).unlink()


def load_doc_lines(path_str: str):
    p = root / path_str
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


problems = []
assembled = 0
for entry in manifest:
    ticker = entry["ticker"]
    src = out_dir / f"{ticker}.json"
    if not src.is_file():
        problems.append(f"{ticker}: 输出文件缺失")
        continue
    data = json.loads(src.read_text(encoding="utf-8"))
    doc_paths = {d["id"]: d["path"] for d in entry["docs"]}
    tasks = data.get("zcode_tasks") or []
    review = data.get("review") or {}
    review_tasks = review.get("tasks") or []
    if {t.get("task_id") for t in tasks} != TASK_IDS:
        problems.append(f"{ticker}: 任务 id 集合异常 -> {sorted({t.get('task_id') for t in tasks})}")
        continue
    if {t.get("task_id") for t in review_tasks} != TASK_IDS:
        problems.append(f"{ticker}: 复核 id 集合异常 -> {sorted({t.get('task_id') for t in review_tasks})}")
        continue
    bad = False
    for t in review_tasks:
        if t.get("status") not in STATUSES:
            problems.append(f"{ticker}/{t.get('task_id')}: 非法状态 {t.get('status')}")
            bad = True
        for mc in (t.get("missing_codes") or []):
            if mc not in MISSING:
                problems.append(f"{ticker}/{t.get('task_id')}: 非法缺口码 {mc}")
                bad = True
        for did in (t.get("evidence_document_ids") or []):
            if did not in doc_paths:
                problems.append(f"{ticker}/{t.get('task_id')}: 证据 id 不在清单 {did}")
                bad = True
        for line in (t.get("evidence_lines") or []):
            did = str(line.get("document_id") or "")
            raw_ref = str(line.get("line_ref") or "").strip()
            ref_num = raw_ref.upper().lstrip("L")
            quote = str(line.get("exact_quote") or "")
            if did not in doc_paths or not ref_num.isdigit():
                problems.append(f"{ticker}/{t.get('task_id')}: 证据行引用无效 {did}/{raw_ref}")
                bad = True
                continue
            lines = load_doc_lines(doc_paths[did])
            lineno = int(ref_num)
            if not (1 <= lineno <= len(lines)):
                problems.append(f"{ticker}/{t.get('task_id')}: 行号越界 {did}/{ref}")
                bad = True
                continue
            if quote and quote not in lines[lineno - 1]:
                problems.append(f"{ticker}/{t.get('task_id')}: 引文与源行不符 {did}/{ref}")
                bad = True
    if bad:
        continue

    report_abs = root / entry["report_path"]
    docs_meta = []
    for d in entry["docs"]:
        p = root / d["path"]
        docs_meta.append({"document_id": d["id"], "path": d["path"], "source_role": d["role"],
                          "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "company": entry["company"],
        "ticker": ticker,
        "scope": "ZCode 独立规则包 v1：规则由 ZCode 直接从主报告正文推导（未读取人工锁定规则），再按封闭协议用本地证据复核；规则不回写、不影响人工裁决。",
        "main_report": {
            "path": entry["report_path"],
            "sha256": hashlib.sha256(report_abs.read_bytes()).hexdigest(),
            "rule_update_mode": "manual_only",
            "automatic_rule_replacement": False,
            "rule_package_source": "zcode_inline_v1",
        },
        "zcode_tasks": tasks,
        "local_evidence_documents": docs_meta,
        "model_review": review,
    }
    atomic_write_json(final_dir / f"{ticker}.json", payload)
    assembled += 1

print(f"组装完成: {assembled}/93 -> {final_dir}")
if problems:
    print(f"问题 {len(problems)} 项:")
    for p in problems:
        print(" -", p)
else:
    print("校验: 全部通过（结构 + 枚举 + 证据归属 + 引文逐字比对）")
