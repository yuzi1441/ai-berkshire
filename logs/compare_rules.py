# 一次性执行记录：人工锁定规则 vs ZCode 独立推导规则，逐股逐任务自动比对。
# 比对维度：任务文本中的数字阈值集合、schedule_type、metrics；输出待语义分类的清单。
import json, re
from pathlib import Path

root = Path(".").resolve()
payload = json.loads((root / "data/investment-dashboard/main_report_resolutions.json").read_text(encoding="utf-8"))
locked = {}
for r in payload["resolutions"]:
    if str(r.get("ticker", "")).upper().endswith((".SH", ".SZ", ".BJ")) and isinstance(r.get("judgment"), dict):
        for t in (r["judgment"].get("review_tasks") or []):
            if t.get("task_id"):
                locked[(r["ticker"], t["task_id"])] = t

NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:元|美元|港元|%|x|倍|亿|万|美元/ADS)")


def nums(text):
    return sorted(m.replace(" ", "") for m in NUM.findall(str(text or "")))


rows = []
for path in sorted((root / "local/fundamental-review-zcode/full-zcode-rules").glob("*.json")):
    zc = json.loads(path.read_text(encoding="utf-8"))
    ticker = zc["ticker"]
    for t in zc.get("zcode_tasks", []):
        key = (ticker, t["task_id"])
        lk = locked.get(key)
        if not lk:
            rows.append({"ticker": ticker, "task_id": t["task_id"], "class": "锁定侧缺失",
                         "zc_content": t.get("content"), "lk_content": None, "zc_nums": nums(t.get("content")), "lk_nums": []})
            continue
        zn, ln = nums(t.get("content")), nums(lk.get("content"))
        if str(t.get("content")) == str(lk.get("content")):
            cls = "文本一致"
        elif zn == ln:
            cls = "数字一致_表述不同"
        elif not zn and not ln:
            cls = "双方无数字阈值"
        else:
            cls = "数字不一致"
        struct = []
        if str(t.get("schedule_type")) != str(lk.get("schedule_type")):
            struct.append(f"schedule:{lk.get('schedule_type')}→{t.get('schedule_type')}")
        lm = sorted(str(x) for x in (lk.get("metrics") or []))
        zm = sorted(str(x) for x in (t.get("metrics") or []))
        if lm != zm:
            struct.append(f"metrics:{lm}→{zm}")
        rows.append({"ticker": ticker, "task_id": t["task_id"], "class": cls,
                     "struct": struct,
                     "lk_content": lk.get("content"), "zc_content": t.get("content"),
                     "lk_nums": ln, "zc_nums": zn,
                     "lk_scope": lk.get("scope_label"), "zc_scope": t.get("scope_label"),
                     "zc_quote": t.get("derivation_quote"), "zc_line": t.get("derivation_line_ref"),
                     "report_path": zc.get("main_report", {}).get("path")})

out = Path("logs/rule_diff.json")
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
import collections
cnt = collections.Counter(r["class"] for r in rows)
print("任务总数:", len(rows))
for k, v in cnt.most_common():
    print(f"  {k}: {v}")
need = [r for r in rows if r["class"] in ("数字不一致", "锁定侧缺失")]
print("需语义分类:", len(need), "条，涉及股票:", len({r['ticker'] for r in need}))
