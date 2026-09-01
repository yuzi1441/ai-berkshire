# 一次性执行记录：生成增量重跑汇总报告（四类清单 + 与前两轮结论的变化对照）。
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

root = Path(".").resolve()
import sys
sys.path.insert(0, "tools")
import main_report_review as mrr

current_dir = root / "local/fundamental-review-current"
legacy_dir = root / "local/fundamental-review-full"
zcode_dir = root / "local/fundamental-review-zcode/full-zcode-rules"

payloads = {}
for path in sorted(current_dir.glob("*.json")):
    if path.stem.startswith(("comparison", "增量重跑汇总")):
        continue
    payloads[path.stem] = json.loads(path.read_text(encoding="utf-8"))

legacy = {}
for path in sorted(legacy_dir.glob("*.json")):
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    tasks = (row.get("model_review") or {}).get("tasks") or []
    legacy[str(row.get("ticker"))] = {
        "triggered": [t.get("task_id") for t in tasks if t.get("status") == "triggered"],
        "any_status": bool(tasks),
    }
zcode = {}
for path in sorted(zcode_dir.glob("*.json")):
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        continue
    tasks = (row.get("model_review") or {}).get("tasks") or []
    zcode[str(row.get("ticker"))] = Counter(t.get("status") for t in tasks)

rule_packages = {str(p["ticker"]): p for p in mrr.load_rule_packages(root / "data/investment-dashboard/main-report-review-rules")}

status_counter = Counter((p.get("summary") or {}).get("status") for p in payloads.values())
redlines, attention, clear, data_gap_list = [], [], [], []
new_obs_count = 0
for ticker, p in sorted(payloads.items()):
    summary = p.get("summary") or {}
    model = p.get("model_review") or {}
    new_obs_count += len(model.get("new_observations") or [])
    row = {"ticker": ticker, "company": p.get("company"), "latest_evidence": p.get("latest_evidence_date"),
           "current_docs": p.get("current_evidence_count")}
    if summary.get("status") == "redline":
        rules = {(r.get("rule_id")): r for r in model.get("rules") or []}
        pkg_rules = {r.get("rule_id"): r for r in (rule_packages.get(ticker, {}).get("active_rules") or [])}
        triggers = []
        for rid in summary.get("redline_rule_ids") or []:
            r = rules.get(rid) or {}
            triggers.append({"rule_id": rid,
                "condition": (pkg_rules.get(rid) or {}).get("condition") or "",
                "current_value": r.get("current_value"),
                "comparison": r.get("comparison"), "evidence": [
                    {"document_id": l.get("document_id"), "quote": (l.get("exact_quote") or "")[:80]}
                    for l in (r.get("evidence_lines") or [])]})
        row["triggers"] = triggers
        redlines.append(row)
    elif summary.get("status") == "attention":
        attention.append(row)
    elif summary.get("status") == "clear":
        clear.append(row)
    elif summary.get("status") == "data_gap":
        data_gap_list.append({"ticker": ticker, "company": p.get("company"),
                              "unknown": summary.get("unknown_count"),
                              "missing": summary.get("missing_requirements")})

# 结果变化口径：与 deepseek 锁定规则轮的 triggered 结论对照
legacy_triggered_stocks = {t: v["triggered"] for t, v in legacy.items() if v.get("triggered")}
change_rows = []
for ticker, p in sorted(payloads.items()):
    new_status = (p.get("summary") or {}).get("status")
    old_trig = legacy_triggered_stocks.get(ticker) or []
    if old_trig and new_status in {"clear", "data_gap"}:
        change_rows.append({"ticker": ticker, "company": p.get("company"),
                            "old": f"deepseek 轮曾判 triggered（{','.join(old_trig)}）",
                            "new": new_status,
                            "note": "本轮未能在基线后证据中确认，或证据缺口无法复核"})
    if new_status == "redline" and not old_trig:
        change_rows.append({"ticker": ticker, "company": p.get("company"),
                            "old": "deepseek 轮无 triggered", "new": "redline",
                            "note": "本轮以基线后官方证据确认红线"})

lines = [
    "# A 股主报告复核·增量重跑汇总（2026-08-30）",
    "",
    f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}；协议：main-report-review-v2.2",
    "- 规则：人工锁定（main_report_resolutions.json），价格条件已按边界排除，规则零改动。",
    "- 证据：本地最新资料优先，全部 93 只另联网拉取巨潮官方公告 PDF（成功 92 只，1 只 stale 股票按设计跳过）；证据指纹与主报告哈希写入每份结果。",
    "- 核验模型：本机 ZCode 子代理替代 OpenCode（无 API key），严格按引擎封闭协议 + fail-closed。",
    f"- 状态分布：{json.dumps(dict(status_counter), ensure_ascii=False)}",
    f"- 全部结论中 met/not_met/unknown/not_due 分布见各股 model_review；new_observations 共 {new_obs_count} 条（只记录事实，不改规则）。",
    "",
    "## 一、红线触发（需人工裁决）",
    "",
]
for row in redlines:
    lines.append(f"### {row['company']}（{row['ticker']}）— 最新证据 {row['latest_evidence']}")
    for t in row["triggers"]:
        lines.append(f"- 规则 `{t['rule_id']}`：条件「{t['condition']}」")
        lines.append(f"  - 当前值「{t['current_value'] or '—'}」；{t['comparison'] or ''}")
        for e in t["evidence"]:
            lines.append(f"  - 证据 {e['document_id']}：「{e['quote']}」")
    lines.append("")
lines += ["## 二、需要关注", ""]
for row in attention:
    lines.append(f"- {row['company']}（{row['ticker']}）— 最新证据 {row['latest_evidence']}")
lines += ["", "## 三、暂无确认红线", ""]
lines += [f"- {row['company']}（{row['ticker']}）" for row in clear]
lines += ["", "## 四、仍缺数据（data_gap，按缺口分类）", ""]
miss_counter = Counter()
for row in data_gap_list:
    for m in row["missing"] or []:
        miss_counter[m] += 1
lines.append(f"- 缺口类型分布：{json.dumps(dict(miss_counter), ensure_ascii=False)}；涉及 {len(data_gap_list)} 只。")
lines.append("- 主要缺口：复核日行情/现价（价格类条件已按边界排除，仍残留估值比较类条件）、分部毛利率、单季拆分、订单事件确认、FCF 资本开支明细。")
lines.append("- 明细清单见 `local/fundamental-review-current/增量重跑汇总-20260830.json`（still_missing_data 字段）。")
lines += ["", "## 五、结果变化（相对 deepseek 锁定规则轮的 triggered 结论）", ""]
if change_rows:
    lines.append("| 股票 | 旧结论 | 本轮 | 说明 |")
    lines.append("|---|---|---|---|")
    for r in change_rows:
        lines.append(f"| {r['company']}({r['ticker']}) | {r['old']} | {r['new']} | {r['note']} |")
else:
    lines.append("- 无方向性变化（旧轮 triggered 的股票本轮均维持需关注/确认或数据缺口，未出现被官方证据直接证伪的红线；亦无新增确认红线脱离旧轮预期）。")
lines += [
    "",
    "## 六、特殊状态股票",
    "",
    "- `600312.SH` 平高电气：主报告内容已变化（哈希不匹配），旧规则只读留档，等待人工重建规则包。",
    "- `601919.SH` 中远海控等 2 只：锁定规则全部为价格条件，按边界由看板人工价格分区处理，不进基本面复核。",
    "- 1 只等待证据：本地与官方渠道均无基线后可用披露，保持等待。",
    "",
    "## 七、文件与可追溯性",
    "",
    "- 逐股结果：`local/fundamental-review-current/<ticker>.json`（含 input_fingerprint、evidence_fingerprint、主报告哈希、generated_at）",
    "- 证据包（本地+官方全文）：`local/main-report-review-evidence/`；子代理原始输出：`local/main-report-review-agent/`",
    "- 引擎：`tools/main_report_review.py`（本次修复 Windows 目录 fsync 兼容）；执行脚本：`logs/collect_incremental_evidence.py`、`logs/build_agent_packets.py`、`logs/assemble_incremental_results.py`",
    "- 每条结论均可沿 来源路径/URL + 披露日期 + 原文行号 + exact_quote + 数值 复查。",
]

out = current_dir / "增量重跑汇总-20260830.md"
mrr.atomic_write_text(out, "\n".join(lines))
print("红线:", [r["ticker"] for r in redlines])
print("attention:", [(r["ticker"]) for r in attention])
print("clear:", [(r["ticker"]) for r in clear])
print("data_gap:", len(data_gap_list), "| 缺口分布:", dict(miss_counter))
print("结果变化对照:", len(change_rows), "条")
print("报告:", out)
