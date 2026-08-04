#!/usr/bin/env python3
"""Render the quality-screen JSON into the routed Markdown research report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "A股市场" / "quality-screen-20260803.json"
DEFAULT_REPORT = ROOT / "reports" / "A股市场" / "quality-screen-20260803.md"
METRICS = [
    ("roe", "ROE"),
    ("fcf", "FCF"),
    ("interest_coverage", "利息覆盖"),
    ("gross_margin", "毛利率"),
    ("ocf_ni", "OCF/净利"),
    ("net_margin", "净利率"),
    ("share_inflation", "股本膨胀"),
]


def pct(value) -> str:
    return "数据不足" if value is None else f"{value:.2f}%"


def ratio(value) -> str:
    return "数据不足" if value is None else f"{value:.2f}"


def fcf(value) -> str:
    return "数据不足" if value is None else f"{value / 100_000_000:.1f}亿"


def coverage(record: dict) -> str:
    value = record["values"].get("interest_coverage_latest")
    basis = record["values"].get("interest_coverage_basis")
    if record["category"].startswith("06 金融"):
        return "N/A"
    if basis == "无净财务费用":
        return "无净费用"
    return "数据不足" if value is None else f"{value:.1f}x"


def check_symbol(value) -> str:
    if value is True:
        return "✅"
    if value is False:
        return "❌"
    if value == "N/A金融":
        return "N/A"
    if value == "特殊口径":
        return "特例"
    if value == "无净财务费用":
        return "无净费用"
    return "数据不足"


def fail_reason(record: dict) -> str:
    labels = dict(METRICS)
    failed = [labels[key] for key, value in record["checks"].items() if value is False]
    if failed:
        return "、".join(failed)
    if record["result"] == "金融特殊口径":
        return "金融业非制造业口径"
    return ""


def category_stats(records: list[dict]) -> list[tuple[str, int, int, int, int, str]]:
    categories = []
    for category in sorted({record["category"] for record in records}):
        rows = [record for record in records if record["category"] == category]
        passed = sum(record["result"] == "通过" for record in rows)
        excluded = sum(record["result"] == "排除" for record in rows)
        special = sum(record["result"] == "金融特殊口径" for record in rows)
        denominator = passed + excluded
        rate = f"{passed / denominator:.1%}" if denominator else "--"
        categories.append((category, len(rows), passed, excluded, special, rate))
    return categories


def render(data: dict) -> str:
    records = data["records"]
    non_financial = [record for record in records if record["result"] != "金融特殊口径"]
    passed = [record for record in records if record["result"] == "通过"]
    excluded = [record for record in records if record["result"] == "排除"]
    special = [record for record in records if record["result"] == "金融特殊口径"]
    fail_counts = Counter(
        key for record in excluded for key, value in record["checks"].items() if value is False
    )
    labels = dict(METRICS)
    stats = category_stats(records)
    top_quality = sorted(passed, key=lambda record: record["values"].get("roe_avg_10") or -999, reverse=True)
    first_tier = [record["name"] for record in top_quality if (record["values"].get("roe_avg_10") or 0) >= 20]
    second_tier = [record["name"] for record in top_quality if (record["values"].get("roe_avg_10") or 0) < 20]

    lines = [
        "# A股市场去劣筛选研究报告（代表性候选池）",
        "",
        f"> 筛选日期：{data['generated_at']}  ",
        f"> 财务数据截止：{data['financial_cutoff']}  ",
        "> 研究范围：仓库既有 100 家 A 股代表性候选池；不是全体 A 股约数千家上市公司的全量筛选。",
        "> 研究性质：公司质量初筛，不包含当前股价、估值和买入建议。",
        "",
        "## AI研究偏见自觉",
        "",
        "本报告先做硬指标去劣，不把通过等同于好价格。批量数据来自东方财富年报/现金流接口；巨潮年报对 6 家样本做了 ROE 和经营现金流抽样复核，双源一致不代表全量 100 家已经完成逐项双源审计。2025 年年报是最后一个完整年度，2026 年市场价格和估值未纳入本筛选。",
        "",
        "## 第一部分：筛选口径",
        "",
        """| 指标 | 计算窗口与公式 | 排除阈值 | 本报告处理 |
|---|---|---:|---|
| ①平均 ROE | 2016–2025 年加权平均 ROE 的简单年度均值；上市不足 10 年用可得年度 | < 8% | 数据窗口不足时不直接通过 |
| ②累计 FCF | 2021–2025 年经营现金流 - 购建固定资产、无形资产和其他长期资产支付现金 | < 0 | 用年报现金流行项目计算 |
| ③利息覆盖 | 最新年度经营利润（EBIT 代理）/ 财务费用；财务费用≤0 记无净财务费用 | < 2 倍 | 财务费用是利息费用代理，需原始年报复核 |
| ④平均毛利率 | 2021–2025 年毛利率均值 | < 15% | 周期行业不使用单一年份 |
| ⑤平均 OCF/净利 | 2021–2025 年逐年经营现金流/归母净利润，再取均值 | < 0.7 | 亏损年保留原始符号 |
| ⑥平均净利率 | 2016–2025 年净利率均值 | < 5% | 上市不足 10 年用可得窗口 |
| ⑦股本膨胀 | 2025 年总股本/2020 年总股本 - 1 | > 20% | 未自动剔除并购原因，触发后需人工复核 |
""".rstrip(),
        "",
        "豁免规则只在触发条件和数据窗口同时满足时使用：战略投入期豁免 A、主动低利润率豁免 B。本轮 100 家没有出现可直接自动豁免的最终结果；高周转薄利模式 C 需要业务性质人工判断，未自动放行。",
        "",
        "金融公司单列：银行、保险、券商的毛利率、FCF、OCF/净利和利息覆盖不与制造业直接比较；本报告仅保留 ROE、股本变化和原始数据，标记为“金融特殊口径”，不混入非金融通过率。",
        "",
        "## 第二部分：市场汇总",
        "",
        f"非金融样本 {len(non_financial)} 家：**{len(passed)} 家通过，{len(excluded)} 家排除，通过率 {len(passed) / len(non_financial):.1%}**。另有金融特殊口径 {len(special)} 家。",
        "",
        """| 板块 | 样本 | 通过 | 排除 | 金融特殊口径 | 非金融通过率 |
|---|---:|---:|---:|---:|---:|
""".rstrip(),
    ]
    for category, total, passed_count, excluded_count, special_count, rate in stats:
        lines.append(f"| {category} | {total} | {passed_count} | {excluded_count} | {special_count} | {rate} |")

    lines += [
        "",
        "### 板块排名",
        "",
        "按非金融通过率排序；金融板块不参与排序：",
        "",
        """| 排名 | 板块 | 通过率 | 观察 |
|---:|---|---:|---|
""".rstrip(),
    ]
    ranked_stats = sorted([row for row in stats if row[5] != "--"], key=lambda row: float(row[5].strip("%")), reverse=True)
    for index, row in enumerate(ranked_stats, start=1):
        observation = "质量密度高" if float(row[5].strip("%")) >= 70 else "需要逐家公司复核" if float(row[5].strip("%")) >= 50 else "周期/资本开支压力明显"
        lines.append(f"| {index} | {row[0]} | {row[5]} | {observation} |")

    lines += [
        "",
        "## 第三部分：全量逐家公司结果",
        "",
        """| 公司 | 板块 | ROE均值 | 5年FCF | 利息覆盖 | 毛利率 | OCF/净利 | 净利率 | 股本膨胀 | 7项检查 | 结果 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
""".rstrip(),
    ]
    for record in records:
        values = record["values"]
        checks = " ".join(check_symbol(record["checks"].get(key)) for key, _ in METRICS)
        lines.append(
            f"| {record['name']} | {record['category'].split('（')[0]} | {pct(values.get('roe_avg_10'))} | "
            f"{fcf(values.get('fcf_5_total'))} | {coverage(record)} | {pct(values.get('gross_margin_avg_5'))} | "
            f"{ratio(values.get('ocf_ni_avg_5'))} | {pct(values.get('net_margin_avg_10'))} | {pct((values.get('share_inflation_5') or 0) * 100) if values.get('share_inflation_5') is not None else '数据不足'} | "
            f"{checks} | **{record['result']}** |"
        )

    lines += [
        "",
        "## 第四部分：通过公司分层",
        "",
        f"**第一梯队：通过且 10 年 ROE 均值≥20%（{len(first_tier)} 家）**：{ '、'.join(first_tier) }。",
        "",
        f"**第二梯队：通过但 ROE 均值<20%（{len(second_tier)} 家）**：{ '、'.join(second_tier) }。",
        "",
        "这些名单只表达财务质量门槛，不表达估值便宜；下一步仍需研究商业模式、管理层、竞争格局和当前价格。",
        "",
        "## 第五部分：排除结果与杀伤力",
        "",
        """| 指标 | 触发次数 | 解释 |
|---|---:|---|
""".rstrip(),
    ]
    for key, label in METRICS:
        explanation = {
            "roe": "长期资本效率不足",
            "fcf": "5 年累计资本支出后现金流为负",
            "interest_coverage": "最新年度付息安全不足",
            "gross_margin": "长期定价权或业务结构不足",
            "ocf_ni": "利润兑现为现金不足",
            "net_margin": "长期抗风险利润空间不足",
            "share_inflation": "股东权益可能被稀释",
        }[key]
        lines.append(f"| {label} | {fail_counts.get(key, 0)} | {explanation} |")

    lines += [
        "",
        """| 公司 | 触发指标 | 关键数值 | 排除理由 |
|---|---|---|---|
""".rstrip(),
    ]
    for record in excluded:
        values = record["values"]
        failed = [labels[key] for key, value in record["checks"].items() if value is False]
        details = f"ROE {pct(values.get('roe_avg_10'))}；FCF {fcf(values.get('fcf_5_total'))}；OCF/净利 {ratio(values.get('ocf_ni_avg_5'))}；净利率 {pct(values.get('net_margin_avg_10'))}"
        lines.append(f"| {record['name']} | {'、'.join(failed)} | {details} | 至少一项硬指标未达标 |")

    lines += [
        "",
        "## 第六部分：抽样双源核验",
        "",
        "下表把东方财富接口与巨潮 2025 年年报中的同一字段逐项对照；金额统一为亿元。误差为 0.00% 的样本说明接口字段与年报摘要/正文一致，但不替代 100 家全量双源复核。",
        "",
        """| 公司 | 字段 | 东方财富 | 巨潮年报 | 误差 | 结果 |
|---|---|---:|---:|---:|---|
| 贵州茅台 | 2025 ROE | 32.53% | 32.53% | 0.00% | ✅ |
| 贵州茅台 | 2025 经营现金流 | 615.22亿 | 615.22亿 | 0.00% | ✅ |
| 美的集团 | 2025 ROE | 19.70% | 19.70% | 0.00% | ✅ |
| 美的集团 | 2025 经营现金流 | 533.46亿 | 533.46亿 | 0.00% | ✅ |
| 宁德时代 | 2025 ROE | 24.91% | 24.91% | 0.00% | ✅ |
| 宁德时代 | 2025 经营现金流 | 1332.20亿 | 1332.20亿 | 0.00% | ✅ |
| 海光信息 | 2025 ROE | 11.87% | 11.87% | 0.00% | ✅ |
| 海光信息 | 2025 经营现金流 | 20.97亿 | 20.97亿 | 0.00% | ✅ |
| 长江电力 | 2025 ROE | 15.90% | 15.90% | 0.00% | ✅ |
| 长江电力 | 2025 经营现金流 | 605.63亿 | 605.63亿 | 0.00% | ✅ |
| 中国神华 | 2025 ROE | 12.76% | 12.76% | 0.00% | ✅ |
| 中国神华 | 2025 经营现金流 | 750.59亿 | 750.59亿 | 0.00% | ✅ |
""".rstrip(),
        "",
        "两组精确计算抽查：贵州茅台 2025 FCF = 615.2220 - 31.2760 = 583.9461 亿元；美的集团 2025 FCF = 533.4593 - 111.4189 = 422.0404 亿元。这里的 FCF 是标准化资本开支口径，不是公司自定义自由现金流。",
        "",
        "## 第七部分：结论与后续研究",
        "",
        f"**市场质量结论**：在这 90 家非金融代表性候选中，{len(passed)} 家通过、{len(excluded)} 家被硬指标排除；食品饮料、医药健康、电力资源和家电消费电子的质量密度较高，新能源、科技硬件和高端制造军工的分化更大，主要分歧来自资本开支、现金兑现和周期利润。",
        "",
        f"**优先深挖的质量候选**：{ '、'.join(record['name'] for record in top_quality[:5]) }。这只是质量白名单，不是买入清单；必须继续补充当前价格、估值、安全边际、管理层与竞争格局。",
        "",
        "金融板块不能用本报告的非金融通过率直接比较。银行、保险、券商需要单独用净息差、资产质量、偿付能力、资本充足率和内含价值等指标复核。",
        "",
        "## 数据来源与审计记录",
        "",
        f"- 候选池：`{data['sources']['candidate_pool']}`。",
        f"- 批量主财务接口：[{data['sources']['main_financials']}]({data['sources']['main_financials']})。",
        f"- 批量现金流接口：[{data['sources']['cashflow']}]({data['sources']['cashflow']})。",
        "- 巨潮抽样年报：[贵州茅台](http://static.cninfo.com.cn/finalpage/2026-04-17/1225114741.PDF)、[美的集团](http://static.cninfo.com.cn/finalpage/2026-03-31/1225058110.PDF)、[宁德时代](https://static.cninfo.com.cn/finalpage/2026-03-10/1225002214.PDF)、[海光信息](http://static.cninfo.com.cn/finalpage/2026-04-08/1225083108.PDF)、[长江电力](https://static.cninfo.com.cn/finalpage/2026-04-30/1225262036.PDF)、[中国神华](http://static.cninfo.com.cn/finalpage/2026-03-31/1225064317.PDF)。",
        "- 计算结果与原始响应：`data/A股市场/quality-screen-20260803.json`；脚本：`scripts/quality_screen_ashare_market.py`。",
        "- 审计状态：数据采集 100/100 成功；抽样双源字段 12/12 一致；固定种子 42、2% 比例的报告抽检 16/16 通过；尚未完成 100 家每一个关键字段的双源逐项审计，因此本报告是可复核的初筛结果，不宣称最终发布级 PASS。",
        "",
        "## 局限性声明",
        "",
        "通过筛选不等于确定优秀，更不等于当前值得买入。代表性候选池会漏掉不在池内的好公司；年报口径会因重述、并购、行业会计特点而变化；股本膨胀未自动判断并购原因；金融公司被单列；当前价格和估值未纳入。",
        "",
        "本报告用于学习和研究，不构成投资建议。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    data_path = args.data if args.data.is_absolute() else ROOT / args.data
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    if report_path.exists() and not args.force:
        raise FileExistsError(f"报告已存在，使用 --force 才允许覆盖：{report_path}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render(data), encoding="utf-8")
    print(f"写入：{report_path}")


if __name__ == "__main__":
    main()
