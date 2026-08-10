"""Compress the 30-stock A-share funnel to a 10-stock research queue."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "A股市场" / "industry-funnel-ashare-30-20260804.json"
DEFAULT_AS_OF = datetime.now().astimezone().strftime("%Y-%m-%d")
DEFAULT_JSON = ROOT / "data" / "A股市场" / f"industry-funnel-ashare-10-{DEFAULT_AS_OF.replace('-', '')}.json"
DEFAULT_CSV = ROOT / "data" / "A股市场" / f"industry-funnel-ashare-10-{DEFAULT_AS_OF.replace('-', '')}.csv"
DEFAULT_REPORT = ROOT / "reports" / "A股去金融周期三次漏斗10家" / f"ashare-quality-funnel-10-{DEFAULT_AS_OF.replace('-', '')}.md"

RISK_NOTES = {
    "601156": "航空货运价格与贸易周期、客户集中度、资产利用率",
    "000858": "白酒需求与渠道库存、批价变化、消费结构",
    "000568": "白酒需求与渠道库存、批价变化、消费结构",
    "600167": "区域供热政策、区域集中度、项目资本开支",
    "000651": "家电需求、价格竞争、地产链和多元化执行",
    "600398": "服饰消费、品牌折扣、加盟/库存管理",
    "603233": "门店扩张效率、并购整合、应付与库存周转",
    "002027": "广告需求、媒体点位成本、应收账款",
    "000513": "药品集采与监管、研发管线、单品依赖",
    "002508": "厨电需求、地产链、渠道和高端竞争",
    "601877": "低压电器价格竞争、海外经营、资本配置",
}


def number(value: object) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_row(row: dict) -> dict:
    old_score = int(row["derived"]["composite_score"])
    moat_score = int(row["moat_quick"]["score"])
    fcf_yield = number(row["derived"].get("fcf_to_market_cap_5y")) or 0
    ocfni = number(row["values"].get("ocf_ni_avg_5")) or 0
    pe = number(row["quote"].get("pe_ttm"))
    market_cap = number(row["quote"].get("market_cap")) or 0
    penalties: list[str] = []
    penalty_points = 0
    if fcf_yield < 0.25:
        penalty_points += 4
        penalties.append("5年FCF/市值<25%")
    if ocfni < 1:
        penalty_points += 2
        penalties.append("OCF/净利<1")
    if pe is not None and pe > 15:
        penalty_points += 2
        penalties.append("PE>15")
    if market_cap < 100 * 100_000_000:
        penalty_points += 2
        penalties.append("市值<100亿")
    row["third_stage"] = {
        "old_composite_score": old_score,
        "moat_weighted_score": moat_score * 2,
        "penalty_points": penalty_points,
        "penalties": penalties,
        "research_score": old_score + moat_score * 2 - penalty_points,
        "main_risk": RISK_NOTES.get(row["code"], "需在公司年报研究中补充失败路径"),
    }
    return row


def select(rows: list[dict]) -> list[dict]:
    ordered = sorted(
        rows,
        key=lambda row: (
            -row["third_stage"]["research_score"],
            -row["third_stage"]["old_composite_score"],
            -int(row["moat_quick"]["score"]),
            -(number(row["quote"].get("market_cap")) or 0),
            row["code"],
        ),
    )
    selected: list[dict] = []
    industry_counts: Counter[str] = Counter()
    for row in ordered:
        industry = row.get("industry") or "未分类"
        if industry_counts[industry] >= 2:
            continue
        selected.append(row)
        industry_counts[industry] += 1
        if len(selected) == 10:
            break
    selected_codes = {row["code"] for row in selected}
    for rank, row in enumerate(selected, 1):
        row["third_stage"]["rank"] = rank
        row["decision_10"] = "入选10家"
        row["decision_reason_10"] = "第三层研究分靠前，护城河初评达到3/5，且未触发行业集中上限"
    for row in rows:
        if row["code"] in selected_codes:
            continue
        if row.get("industry") in {item.get("industry") for item in selected}:
            row["decision_10"] = "淘汰"
            row["decision_reason_10"] = "第三层研究分未进入前10；同业需优先研究得分更高者"
        else:
            row["decision_10"] = "淘汰"
            row["decision_reason_10"] = "第三层研究分未进入前10"
    return selected


def fmt(value: object, digits: int = 2) -> str:
    number_value = number(value)
    return "数据不足" if number_value is None else f"{number_value:.{digits}f}"


def fmt_yi(value: object) -> str:
    number_value = number(value)
    return "数据不足" if number_value is None else f"{number_value / 100_000_000:.1f}"


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank", "code", "name", "exchange", "industry", "decision_10", "decision_reason_10",
        "price", "market_cap_yi", "pe_ttm", "pb", "old_composite_score", "moat_rating",
        "research_score", "penalty_points", "penalties", "roe_avg_10", "ocf_ni_avg_5",
        "fcf_to_market_cap_5y", "main_risk", "quote_cross_check", "quote_timestamp",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            quote = row.get("quote") or {}
            values = row.get("values") or {}
            stage = row.get("third_stage") or {}
            cross = row.get("quote_cross_check") or {}
            writer.writerow(
                {
                    "rank": stage.get("rank"),
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "exchange": row.get("exchange"),
                    "industry": row.get("industry"),
                    "decision_10": row.get("decision_10"),
                    "decision_reason_10": row.get("decision_reason_10"),
                    "price": quote.get("price"),
                    "market_cap_yi": (number(quote.get("market_cap")) or 0) / 100_000_000 if quote.get("market_cap") is not None else None,
                    "pe_ttm": quote.get("pe_ttm"),
                    "pb": quote.get("pb"),
                    "old_composite_score": stage.get("old_composite_score"),
                    "moat_rating": row.get("moat_quick", {}).get("rating"),
                    "research_score": stage.get("research_score"),
                    "penalty_points": stage.get("penalty_points"),
                    "penalties": ";".join(stage.get("penalties") or []),
                    "roe_avg_10": values.get("roe_avg_10"),
                    "ocf_ni_avg_5": values.get("ocf_ni_avg_5"),
                    "fcf_to_market_cap_5y": row.get("derived", {}).get("fcf_to_market_cap_5y"),
                    "main_risk": stage.get("main_risk"),
                    "quote_cross_check": cross.get("status"),
                    "quote_timestamp": cross.get("provider_timestamp"),
                }
            )


def build_report(payload: dict, path: Path) -> None:
    selected = sorted(
        [row for row in payload["records"] if row.get("decision_10") == "入选10家"],
        key=lambda row: row["third_stage"].get("rank", 999),
    )
    reasons = Counter(row.get("decision_reason_10") for row in payload["records"] if row.get("decision_10") != "入选10家")
    industry_counts = Counter(row.get("industry") or "未分类" for row in selected)
    lines = [
        "# A股去金融与周期后的三次漏斗：10家优先研究名单",
        "",
        f"> 研究日期：{payload['as_of']}  ",
        f"> 财务数据截止：{payload['financial_cutoff']}  ",
        f"> 行情快照：2026-08-04，继承上一层腾讯行情时间 {payload['quote_timestamp']}  ",
        "> 市场范围：沪深京 A 股；本报告从上一层 30 家候选继续压缩。  ",
        "> 研究性质：优先研究名单，不等同于买入清单或投资建议。",
        "",
        "## 结论",
        "",
        f"从上一层 30 家中，按第三层研究分筛出 {len(selected)} 家。研究分 = 上一层综合分 + 护城河初评分×2 - 风险扣分；风险扣分针对现金流转换、5年 FCF/市值、PE 和市值，不替代逐家公司基本面研究。",
        "",
        "这 10 家是下一轮年报、管理层、竞争格局和估值安全边际研究的优先队列，不是同时买入的组合。当前价格仍是 2026-08-04 快照，不能直接外推为今天的价格。",
        "",
        "## 漏斗记录",
        "",
        "| 层级 | 家数 | 规则 |",
        "|---|---:|---|",
        f"| 上一层候选 | {payload['input_counts']['stage_30']} | 质量、估值和行业分散后的30家 |",
        f"| 护城河初评达标 | {payload['input_counts']['moat_ready']} | 初评至少3/5，仍需年报核验 |",
        f"| 最终优先研究 | {len(selected)} | 研究分排序 + 单一行业最多2家 |",
        "",
        "## 第三层口径",
        "",
        "- 研究分：上一层综合分 + 护城河初评分×2。",
        "- 扣 4 分：5年累计 FCF/当前市值 < 25%。",
        "- 扣 2 分：OCF/净利润 < 1、PE > 15、市值 < 100 亿元，各项可叠加。",
        "- 单一细分行业最多 2 家；这是分散约束，不是行业质量判断。",
        "",
        "## 10家优先研究名单",
        "",
        "| 排名 | 公司 | 代码 | 行业 | 价格 | 市值(亿元) | PE | PB | 上层分 | 护城河 | 扣分 | 研究分 | 当前定位 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|",
    ]
    for row in selected:
        quote = row.get("quote") or {}
        stage = row.get("third_stage") or {}
        fcf_yield = number(row.get("derived", {}).get("fcf_to_market_cap_5y")) or 0
        pe = number(quote.get("pe_ttm"))
        positioning = "当前估值较友好" if pe is not None and pe <= 12 and fcf_yield >= 0.25 else "质量优先，估值跟踪"
        lines.append(
            f"| {stage.get('rank')} | {row.get('name')} | {row.get('code')}.{row.get('exchange')} | {row.get('industry') or '未分类'} | {fmt(quote.get('price'))} | {fmt_yi(quote.get('market_cap'))} | {fmt(quote.get('pe_ttm'))} | {fmt(quote.get('pb'))} | {stage.get('old_composite_score')} | {row.get('moat_quick', {}).get('rating')} | {'、'.join(stage.get('penalties') or []) or '无'} | {stage.get('research_score')} | {positioning} |"
        )
    lines.extend(
        [
            "",
            "## 主要风险",
            "",
            "| 公司 | 首要需要验证的风险 |",
            "|---|---|",
        ]
    )
    for row in selected:
        lines.append(f"| {row.get('name')} | {row.get('third_stage', {}).get('main_risk')} |")
    lines.extend(
        [
            "",
            "## 30家中未进入10家的记录",
            "",
            "| 淘汰原因 | 家数 |",
            "|---|---:|",
        ]
    )
    for reason, count in reasons.most_common():
        lines.append(f"| {reason} | {count} |")
    lines.extend(
        [
            "",
            "## 审计状态与下一步",
            "",
            "- 上一层 30 家已完成价格两源核对和市值验算；本层沿用同一快照，10 家是其子集。",
            "- 护城河分数是研究初评，不是已完成的年报证据审计；下一步应对10家公司逐一补充东方财富 + 巨潮年报、管理层资本配置和历史估值分位。",
            "- 本名单不输出买入价和仓位，避免把研究优先级误写成当前买入优先级。",
            "",
            "## AI研究偏见自觉",
            "",
            "本层偏向有较高历史质量分、现金流好、估值可比和护城河初评较高的公司，可能低估处于转型早期但短期财务较弱的公司；小市值扣分也会牺牲部分高成长候选。",
            "",
            "## 来源",
            "",
            f"- 上一层数据：`{payload['input_path']}`。",
            "- 估值与价格：上一层东方财富行情 + 腾讯价格快照。",
            "- 财务数据截止：2025-12-31；当前报告未新增2026年季度数据。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    rows = []
    for source_row in source["records"]:
        if source_row.get("decision") != "入选30家":
            continue
        row = json.loads(json.dumps(source_row, ensure_ascii=False))
        score_row(row)
        rows.append(row)
    selected = select(rows)
    del selected
    payload = {
        "schema_version": 1,
        "as_of": args.as_of,
        "financial_cutoff": source.get("financial_cutoff", "2025-12-31"),
        "quote_timestamp": source.get("quote_timestamp"),
        "scope": "沪深京A股；去金融与周期后的30家候选继续压缩到10家",
        "input_path": str(args.input),
        "input_counts": {
            "stage_30": len(rows),
            "moat_ready": sum(int(row.get("moat_quick", {}).get("score") or 0) >= 3 for row in rows),
        },
        "rules": {
            "research_score": "上一层综合分 + 护城河初评分*2 - 风险扣分",
            "penalty_fcf_yield": "5年累计FCF/当前市值<25%: -4",
            "penalty_ocf_ni": "5年OCF/净利润<1: -2",
            "penalty_pe": "PE>15: -2",
            "penalty_market_cap": "总市值<100亿元: -2",
            "industry_cap": 2,
            "selection_count": 10,
        },
        "counts": dict(Counter(row.get("decision_10") for row in rows)),
        "records": rows,
        "json_path": str(args.json),
        "csv_path": str(args.csv),
        "report_path": str(args.report),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(rows, args.csv)
    build_report(payload, args.report)
    print(json.dumps({"json": str(args.json), "csv": str(args.csv), "report": str(args.report), "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
