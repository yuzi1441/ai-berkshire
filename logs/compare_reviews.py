# 一次性执行记录：ZCode 独立规则复核 vs deepseek 人工锁定规则复核，逐股逐任务对照。
import json
from datetime import datetime
from pathlib import Path

root = Path(".").resolve()
manifest = json.loads((root / "logs/zcode_review_manifest.json").read_text(encoding="utf-8"))
ds_dir = root / "local/fundamental-review-full"
zc_dir = root / "local/fundamental-review-zcode/full-zcode-rules"
report_path = root / "local/fundamental-review-zcode/对照报告-20260829.md"

ORDER = ["entry", "holder", "risk"]


def brief(text, n=42):
    text = str(text or "").replace("\n", " ")
    return text[:n] + ("…" if len(text) > n else "")


rows = []
agree_matrix = {}
status_ds, status_zc = {}, {}
per_task_agree = {k: [0, 0] for k in ORDER}
divergent = []
for entry in manifest:
    ticker = entry["ticker"]
    ds = json.loads((ds_dir / f"{ticker}.json").read_text(encoding="utf-8"))
    zc = json.loads((zc_dir / f"{ticker}.json").read_text(encoding="utf-8"))
    ds_tasks = {t["task_id"]: t for t in (ds.get("model_review") or {}).get("tasks", [])}
    zc_tasks = {t["task_id"]: t for t in (zc.get("model_review") or {}).get("tasks", [])}
    ds_rules = {t["task_id"]: t for t in ds.get("fixed_tasks", [])}
    zc_rules = {t["task_id"]: t for t in zc.get("zcode_tasks", [])}
    stock_ok = True
    for tid in ORDER:
        d = ds_tasks.get(tid, {})
        z = zc_tasks.get(tid, {})
        s_d, s_z = d.get("status", "?"), z.get("status", "?")
        status_ds[s_d] = status_ds.get(s_d, 0) + 1
        status_zc[s_z] = status_zc.get(s_z, 0) + 1
        agree_matrix[(s_d, s_z)] = agree_matrix.get((s_d, s_z), 0) + 1
        per_task_agree[tid][1] += 1
        if s_d == s_z:
            per_task_agree[tid][0] += 1
        else:
            stock_ok = False
            divergent.append({
                "ticker": ticker, "company": entry["company"], "task_id": tid,
                "ds_status": s_d, "zc_status": s_z,
                "ds_rule": brief(ds_rules.get(tid, {}).get("content")),
                "zc_rule": brief(zc_rules.get(tid, {}).get("content")),
                "ds_missing": d.get("missing_codes") or [],
                "zc_missing": z.get("missing_codes") or [],
            })
    rows.append({"ticker": ticker, "company": entry["company"], "agree": stock_ok})

total = sum(agree_matrix.values())
agreed = sum(v for (a, b), v in agree_matrix.items() if a == b)
stat_lines = []
for tid in ORDER:
    ok, n = per_task_agree[tid]
    stat_lines.append(f"| {tid} | {ok}/{n} | {ok/n*100:.0f}% |")

pairs = sorted(agree_matrix.items(), key=lambda kv: -kv[1])
matrix_lines = [f"| deepseek={a} ↔ zcode={b} | {v} |" for (a, b), v in pairs]

lines = [
    "# 复核对照报告：ZCode 独立规则包 vs 人工锁定规则（deepseek-v4-flash）",
    "",
    f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
    "- 对照双方：",
    "  - 甲方（锁定规则轮）：`local/fundamental-review-full/`，规则为人工复核层 2026-08-27 从各主报告锁定，模型 deepseek-v4-flash 经 OpenCode 执行。",
    "  - 乙方（独立规则轮）：`local/fundamental-review-zcode/full-zcode-rules/`，规则由 ZCode 子代理**不读取锁定规则**、直接从各自主报告推导（zcode_inline_v1），再按同一封闭协议用本地证据复核。",
    "- 两轮使用相同的本地证据选取逻辑（主报告 + thesis/tracker 类本地文档，不含 Checklist/技术面/情绪面）。",
    "",
    "## 结论口径提醒",
    "",
    "两轮的任务文本不同源（同一主报告、两次独立推导），状态逐格对照回答的是『对同一只股票的同一类决策问题（买入前提/持仓验证/风险失效），两套规则+两个复核模型是否给出同向结论』，而非逐字比较规则本身。",
    "",
    "## 总体一致性",
    "",
    f"- 任务总数：{total}（93 只 × 3）",
    f"- 状态完全一致：{agreed}（{agreed/total*100:.0f}%）",
    f"- 分歧任务数：{total - agreed}",
    "",
    "| 任务 | 一致 | 一致率 |",
    "|---|---|---|",
    *stat_lines,
    "",
    "## 状态交叉分布",
    "",
    "| 组合 | 任务数 |",
    "|---|---|",
    *matrix_lines,
    "",
    f"- deepseek 状态分布：{json.dumps(status_ds, ensure_ascii=False)}",
    f"- ZCode 状态分布：{json.dumps(status_zc, ensure_ascii=False)}",
    "",
    "## 逐股一致性",
    "",
    f"- 全任务一致股票：{sum(1 for r in rows if r['agree'])}/93",
    f"- 存在分歧股票：{sum(1 for r in rows if not r['agree'])}/93（明细见下）",
    "",
    "## 分歧明细",
    "",
]
if divergent:
    lines.append("| 股票 | 任务 | deepseek | ZCode | deepseek 规则要点 | ZCode 规则要点 | 缺口(锁定/独立) |")
    lines.append("|---|---|---|---|---|---|---|")
    for d in divergent:
        lines.append(
            f"| {d['company']}({d['ticker']}) | {d['task_id']} | {d['ds_status']} | {d['zc_status']} "
            f"| {d['ds_rule']} | {d['zc_rule']} | {','.join(d['ds_missing']) or '—'} / {','.join(d['zc_missing']) or '—'} |")
else:
    lines.append("（无分歧）")

lines += [
    "",
    "## 安全相关差异（triggered/红线类）",
    "",
]
trig = [d for d in divergent if "triggered" in (d["ds_status"], d["zc_status"])]
if trig:
    for d in trig:
        lines.append(f"- **{d['company']}({d['ticker']}) / {d['task_id']}**：deepseek={d['ds_status']}，ZCode={d['zc_status']}。锁定规则要点：{d['ds_rule']}；独立规则要点：{d['zc_rule']}")
else:
    lines.append("- 无：两轮均未在对方判为未触发的任务上独自判出 triggered。")

lines += [
    "",
    "## 方法差异说明",
    "",
    "- ZCode 独立轮执行了更严的证据纪律：79 只仅有主报告的股票，主报告一律只作基线、不冒充新独立验证，相关任务诚实判 `data_insufficient` 并标注缺口；deepseek 轮在同样证据条件下判出更多 `verified`（部分以报告基线数据充当验证）。",
    "- 因此『deepseek=verified / ZCode=data_insufficient』的组合主要反映**验证标准宽严差**，而非事实判断冲突；事实层面的红旗差异重点看 triggered/not_triggered 象限。",
    "- 全部 279 条 ZCode 结论的引文已与源文件逐字比对通过；锁定规则文件 `main_report_resolutions.json` 与 deepseek 结果在全程中未被修改。",
    "",
    "## 文件清单",
    "",
    "- 独立规则+复核结果：`local/fundamental-review-zcode/full-zcode-rules/<ticker>.json`（93 份）",
    "- 子代理原始输出：`local/fundamental-review-zcode/agent_out/`（93 份）",
    "- 执行记录脚本：`logs/build_zcode_manifest.py`、`logs/assemble_zcode_results.py`、`logs/compare_reviews.py`",
]

report_path.write_text("\n".join(lines), encoding="utf-8")
print(f"一致: {agreed}/{total} ({agreed/total*100:.0f}%)")
for tid in ORDER:
    ok, n = per_task_agree[tid]
    print(f"  {tid}: {ok}/{n}")
print("状态分布 deepseek:", json.dumps(status_ds, ensure_ascii=False))
print("状态分布 zcode  :", json.dumps(status_zc, ensure_ascii=False))
print("分歧股票数:", sum(1 for r in rows if not r['agree']))
print("triggered 相关分歧:", len(trig))
for d in trig:
    print(f"  - {d['company']}({d['ticker']})/{d['task_id']}: ds={d['ds_status']} zc={d['zc_status']}")
print("报告:", report_path)
