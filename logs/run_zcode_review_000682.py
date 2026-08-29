# 一次性执行记录：ZCode 代理担任复核模型，完成 000682.SZ 锁定任务语义核验。
# 复核输入（任务目录/证据目录）由 fundamental_review_radar 自身函数生成，
# 人工锁定规则未被修改；输出写入 local/fundamental-review-zcode/，不覆盖 Mac 全量结果。
import sys
from pathlib import Path

sys.path.insert(0, "tools")
import fundamental_review_radar as radar

root = Path(".").resolve()
res = next(r for r in radar.load_a_share_resolutions(root) if r["ticker"] == "000682.SZ")
docs = radar.collect_local_stock_evidence(root, res)

model_result = {
    "status": "completed",
    "rule_update": "manual_only",
    "model": "zcode-inline-review/GLM（本机 ZCode 代理担任复核模型，非 OpenCode）",
    "reasoning": (
        "按封闭协议逐条核验 main_report_resolutions.json 中人工锁定的 3 个任务；"
        "证据仅限 document_catalog 内本地文档（主报告基线 + 2026-08-19 半年报跟踪 + thesis），"
        "未使用外部知识，未新增/删除/放宽任何阈值。本地证据价格与财务截至 2026-08-19/08-20 披露周期，"
        "执行层面需以最新行情复核价格分支。"
    ),
    "tasks": [
        {
            "task_id": "entry",
            "status": "verified",
            "evidence_document_ids": ["local_1", "local_2"],
            "evidence_lines": [
                {
                    "document_id": "local_1",
                    "line_ref": "L365",
                    "exact_quote": "| 空仓者 | 不建议追逐“AI+电网”情绪买入。12 元附近可建观察仓；10-11 元若基本面未坏，性价比更好。 |",
                },
                {
                    "document_id": "local_2",
                    "line_ref": "L68",
                    "exact_quote": "2026-08-19 收盘价为 11.58 元，腾讯与新浪两源一致。按总股本 13.40727 亿股复算，总市值 155.26 亿元",
                },
                {
                    "document_id": "local_2",
                    "line_ref": "L78",
                    "exact_quote": "成本仍位于原报告 10–13 元的小仓观察区间，价格没有失去安全边际；但“价格不贵”不能抵消毛利率、现金流和资本配置的不确定性。10% 继续作为仓位上限。",
                },
            ],
            "missing_codes": ["no_current_value"],
        },
        {
            "task_id": "holder",
            "status": "verified",
            "evidence_document_ids": ["local_2"],
            "evidence_lines": [
                {
                    "document_id": "local_2",
                    "line_ref": "L25",
                    "exact_quote": "| 扣非归母净利润 | 3.18 亿元，+7.76% | 低于论文长期两位数增长阈值 |",
                },
                {
                    "document_id": "local_2",
                    "line_ref": "L26",
                    "exact_quote": "| 综合毛利率 | 30.68%，同比下降约 2.40 个百分点 | 低于 31% 跟踪阈值，但仍高于 30% 红线 |",
                },
                {
                    "document_id": "local_2",
                    "line_ref": "L27",
                    "exact_quote": "| 经营现金流净额 | -7.70 亿元，上年同期 -5.51 亿元 | 季节性仍在，但同比恶化 39.79% |",
                },
            ],
            "missing_codes": ["no_event_confirmation"],
        },
        {
            "task_id": "risk",
            "status": "not_triggered",
            "evidence_document_ids": ["local_2"],
            "evidence_lines": [
                {
                    "document_id": "local_2",
                    "line_ref": "L39",
                    "exact_quote": "| 1 | 营收与扣非利润长期同比增长不低于 10% | 收入 +15.98%，扣非利润 +7.76%；Q2 单季收入 +22.32%、扣非利润 +6.55% | 🟡 |",
                },
                {
                    "document_id": "local_2",
                    "line_ref": "L26",
                    "exact_quote": "| 综合毛利率 | 30.68%，同比下降约 2.40 个百分点 | 低于 31% 跟踪阈值，但仍高于 30% 红线 |",
                },
                {
                    "document_id": "local_2",
                    "line_ref": "L68",
                    "exact_quote": "2026-08-19 收盘价为 11.58 元，腾讯与新浪两源一致。",
                },
            ],
            "missing_codes": ["no_current_value"],
        },
    ],
}

payload = radar.full_local_result(root, res, docs, model_result)
out_dir = root / "local" / "fundamental-review-zcode"
out_dir.mkdir(parents=True, exist_ok=True)
radar.atomic_write_json(out_dir / "000682.SZ.json", payload)

mac = __import__("json").loads(
    (root / "local" / "fundamental-review-full" / "000682.SZ.json").read_text(encoding="utf-8")
)
print("=== ZCode 复核（本次）vs Mac deepseek-v4-flash ===")
mac_tasks = {t["task_id"]: t for t in (mac.get("model_review") or {}).get("tasks", [])}
for task in model_result["tasks"]:
    ref = mac_tasks.get(task["task_id"], {})
    print(
        f"{task['task_id']}: ZCode={task['status']} | deepseek={ref.get('status')}"
        f" | 缺口 ZCode={task['missing_codes']} deepseek={ref.get('missing_codes')}"
    )
print("输出:", out_dir / "000682.SZ.json")
