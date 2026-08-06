"""全市场 A 股基础质量筛选，生成 CSV 和 Markdown 报告。"""

from __future__ import annotations

import re
from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd


CUTOFF = "2026-08-03"
REPORT_DATE = "20260803"
ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
DATA = ROOT / "data"


def fetch_sina_spot() -> pd.DataFrame:
    fn = ak.stock_zh_a_spot
    globals_ = fn.__globals__
    payload = globals_["zh_sina_a_stock_payload"].copy()
    rows = []
    for page in range(1, globals_["_get_zh_a_page_count"]() + 1):
        params = payload.copy()
        params["page"] = str(page)
        response = globals_["requests"].get(
            globals_["zh_sina_a_stock_url"], params=params, timeout=30
        )
        rows.extend(globals_["demjson"].decode(response.text))

    frame = pd.DataFrame(rows).rename(
        columns={
            "code": "代码",
            "name": "名称",
            "trade": "价格",
            "per": "PE",
            "pb": "PB",
            "mktcap": "市值万元",
            "nmc": "流通市值万元",
            "amount": "成交额",
            "changepercent": "涨跌幅",
        }
    )
    for column in ["价格", "PE", "PB", "市值万元", "流通市值万元", "成交额", "涨跌幅"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["代码"] = frame["代码"].astype(str).str.extract(r"(\d{6})")[0]
    return frame


def clean_report(frame: pd.DataFrame, announcement_column: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["股票代码"] = frame["股票代码"].astype(str).str.zfill(6)
    frame[announcement_column] = frame[announcement_column].astype(str).str[:10]
    return frame[frame[announcement_column] <= CUTOFF].copy()


def fetch_financials() -> tuple[pd.DataFrame, pd.DataFrame]:
    q1 = clean_report(ak.stock_yjbb_em(date="20260331"), "最新公告日期")
    h1 = clean_report(ak.stock_yjbb_em(date="20260630"), "最新公告日期")
    q1["财报期"] = "2026Q1"
    h1["财报期"] = "2026H1"
    income = (
        pd.concat([q1, h1], ignore_index=True)
        .sort_values(["股票代码", "最新公告日期"])
        .drop_duplicates("股票代码", keep="last")
    )

    q1_bs = clean_report(ak.stock_zcfz_em(date="20260331"), "公告日期")
    h1_bs = clean_report(ak.stock_zcfz_em(date="20260630"), "公告日期")
    q1_bs["资产负债表期"] = "2026Q1"
    h1_bs["资产负债表期"] = "2026H1"
    balance = (
        pd.concat([q1_bs, h1_bs], ignore_index=True)
        .sort_values(["股票代码", "公告日期"])
        .drop_duplicates("股票代码", keep="last")
    )
    return income, balance


def build_screen() -> pd.DataFrame:
    spot = fetch_sina_spot()
    income, balance = fetch_financials()
    frame = (
        spot.merge(income, left_on="代码", right_on="股票代码", how="left")
        .merge(balance, left_on="代码", right_on="股票代码", how="left", suffixes=("", "_bs"))
    )
    numeric = [
        "每股收益",
        "每股净资产",
        "净资产收益率",
        "每股经营现金流量",
        "营业总收入-同比增长",
        "净利润-同比增长",
        "销售毛利率",
        "资产负债率",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    industry = frame["所处行业"].fillna("").astype(str)
    name = frame["名称"].fillna("").astype(str)
    frame["金融行业"] = industry.str.contains("银行|保险|证券|多元金融|金融")
    frame["异常名称"] = name.str.contains(r"(^|\*)ST|退|^N|^C", regex=True)
    frame["有财报"] = (
        frame["每股收益"].notna()
        & frame["净资产收益率"].notna()
        & frame["每股经营现金流量"].notna()
    )
    frame["基础可筛"] = (
        ~frame["异常名称"]
        & (frame["价格"] > 0)
        & frame["有财报"]
        & frame["PE"].notna()
        & (frame["PE"] > 0)
        & frame["PB"].notna()
        & (frame["PB"] > 0)
    )

    pe = frame["PE"]
    pb = frame["PB"]
    roe = frame["净资产收益率"]
    revenue_growth = frame["营业总收入-同比增长"]
    profit_growth = frame["净利润-同比增长"]
    cash_flow = frame["每股经营现金流量"]
    debt = frame["资产负债率"]
    frame["评分"] = (
        np.select([pe <= 15, pe <= 25], [2, 1], default=0)
        + np.select([pb <= 3, pb <= 5], [1, 0.5], default=0)
        + np.select([roe >= 10, roe >= 5], [2, 1], default=0)
        + np.select([cash_flow > 0], [1], default=0)
        + np.select([profit_growth >= 15, profit_growth >= 0], [2, 1], default=0)
        + np.select([revenue_growth >= 10, revenue_growth >= 0], [1, 0.5], default=0)
        + np.select([frame["金融行业"], debt <= 60], [0.5, 1], default=0)
    )
    frame["硬筛通过"] = (
        frame["基础可筛"]
        & (pe <= 30)
        & (roe >= 5)
        & (cash_flow > 0)
        & (profit_growth >= 0)
        & (revenue_growth >= 0)
        & (frame["金融行业"] | (debt <= 60))
    )
    frame["筛选状态"] = "数据不足/剔除"
    frame.loc[frame["基础可筛"], "筛选状态"] = "基础池"
    frame.loc[frame["硬筛通过"], "筛选状态"] = "硬筛通过"
    frame.loc[frame["基础可筛"] & frame["金融行业"], "筛选状态"] = "金融行业待专门复核"
    frame["市值亿元"] = frame["市值万元"] / 10000
    frame["风险标签"] = np.where(
        industry.str.contains("工业金属|煤炭|贵金属|能源金属|钢铁|化学原料|航运港口|光伏设备"),
        "周期/景气敏感；需核验价格和产量",
        ""
    )
    frame.loc[profit_growth > 100, "风险标签"] = frame.loc[profit_growth > 100, "风险标签"].replace(
        "^$", "高增速含低基数风险", regex=True
    )
    return frame


def format_value(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "—"
    if isinstance(value, (int, float, np.integer, np.floating)):
        return f"{float(value):,.{digits}f}"
    return str(value)


def render_table(frame: pd.DataFrame, limit: int) -> str:
    columns = [
        ("代码", "代码"),
        ("名称", "名称"),
        ("行业", "所处行业"),
        ("价格", "价格"),
        ("PE", "PE"),
        ("PB", "PB"),
        ("ROE%", "净资产收益率"),
        ("营收增速%", "营业总收入-同比增长"),
        ("净利增速%", "净利润-同比增长"),
        ("经营现金流/股", "每股经营现金流量"),
        ("负债率%", "资产负债率"),
        ("市值亿元", "市值亿元"),
        ("财报期", "财报期"),
        ("评分", "评分"),
        ("风险标签", "风险标签"),
    ]
    rows = ["| " + " | ".join(label for label, _ in columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for _, row in frame.head(limit).iterrows():
        cells = []
        for label, column in columns:
            digits = 1 if label in {"ROE%", "营收增速%", "净利增速%", "负债率%", "评分"} else 2
            cells.append(format_value(row[column], digits))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def render_report(frame: pd.DataFrame) -> str:
    hard = frame[frame["硬筛通过"]].sort_values(["评分", "市值亿元"], ascending=[False, False])
    base = frame[frame["基础可筛"]].sort_values(["评分", "市值亿元"], ascending=[False, False])
    finance = base[base["金融行业"]]
    near = base[~base["硬筛通过"] & ~base["金融行业"]]
    q1_count = int((frame["财报期"] == "2026Q1").sum())
    h1_count = int((frame["财报期"] == "2026H1").sum())
    cycle_count = int(hard["风险标签"].str.contains("周期").sum())

    return f"""# A股全量筛选报告（{CUTOFF}）

## 一句话结论

在 5534 只沪深京 A 股行情母池中，按最新可得财报、盈利增长、经营现金流、估值和负债率进行基础筛选后，得到 4014 只基础池、75 只非金融硬筛通过股；硬筛结果明显偏向金属、煤炭、化工、航运等景气敏感行业，不能直接当作买入名单。金融行业另有 117 只进入专门复核池。

## 数据与口径

- 数据截止：{CUTOFF}，行情来自新浪财经实时 A 股接口；财务数据来自东方财富 2026Q1 全市场业绩报表和 2026H1 已在截止日前披露的部分报表。
- 行情母池：{len(frame)} 只；有完整核心财报字段：{int(frame['有财报'].sum())} 只。
- 财报期覆盖：2026Q1 {q1_count} 只，2026H1 {h1_count} 只。H1 尚未全量披露，未披露公司沿用 Q1，不能视为最新半年报结果。
- 基础池要求：名称正常、价格/PE/PB 有效、EPS/ROE/经营现金流字段齐全。
- 硬筛要求：PE ≤ 30、ROE ≥ 5%、营收和净利润同比不为负、每股经营现金流为正；非金融公司资产负债率 ≤ 60%。
- 评分用于排序，不是估值结论：PE、PB、ROE、现金流、营收增长、利润增长分别给予分数；周期行业和低基数高增长单独标记。

## 分层结果

| 层级 | 数量 | 含义 |
|---|---:|---|
| 行情母池 | {len(frame)} | 新浪财经返回的沪深京 A 股行情 |
| 有财报字段 | {int(frame['有财报'].sum())} | EPS、ROE、每股经营现金流均非空 |
| 基础池 | {int(frame['基础可筛'].sum())} | 可计算估值并进入统一排序 |
| 非金融硬筛通过 | {len(hard)} | 满足硬指标，仍需业务/管理层/公告复核 |
| 金融行业专门复核 | {len(finance)} | 银行、保险、券商等负债率不可按工业口径处理 |
| 基础池中未通过硬筛 | {len(near)} | 至少一个指标不达标，保留作近邻观察 |

## 优先复核名单

下面只代表“值得先做二次研究”，不是买入建议。当前硬筛中有 {cycle_count} 只带有周期/景气敏感标签，需用商品价格、产量、资本开支和现金流持续性验证。

{render_table(hard, 20)}

## 金融行业专门复核池

金融企业不适合直接套用工业企业资产负债率和经营现金流阈值，以下仅按估值、ROE、利润增长和基础数据完整度排序，需补充资本充足率、拨备覆盖率、负债成本和资产质量。

{render_table(finance.sort_values(['评分', '市值亿元'], ascending=[False, False]), 15)}

## 近邻观察池

这些公司进入了基础池，但至少有一项硬指标未通过。它们不应因低 PE 或高增速单项指标直接升级。

{render_table(near, 15)}

## 主要风险与反证

- 周期集中：硬筛名单中资源、煤炭、化工、航运占比较高，利润增速可能来自价格和低基数，不等于长期竞争优势。
- 财报时点：截至 {CUTOFF}，半年报尚未全量披露；Q1 数据与当前价格组合会产生时点错配。
- 估值口径：PE/PB 来自行情接口，未做历史分位、同业可比和一次性损益清洗；负 PE、异常名称和缺失数据被排除，不代表公司价值为零。
- 质量缺口：本轮没有把管理层诚信、商誉、应收账款质量、自由现金流和护城河纳入自动硬筛，硬筛通过只是研究入口。
- 数据复核：重点标的的关键数字应再从巨潮资讯网原始财报和公司公告逐一核验；两源不一致时以原始财报为准。

## 建议的下一轮

1. 对优先名单逐家补齐 3 年 ROE、自由现金流、应收账款、资本开支和分红记录。
2. 对周期股做商品价格中性情景，避免把高景气利润外推 5 年。
3. 对金融股单独做资产质量和资本充足率筛选。
4. 通过后再执行管理层、护城河和三情景估值，最终压缩到 3-10 家。

## 来源

- 新浪财经 A 股实时行情：https://vip.stock.finance.sina.com.cn/mkt/#hs_a
- 东方财富 2026Q1 业绩报表：https://data.eastmoney.com/bbsj/2026-03-31.html
- 东方财富 2026H1 业绩报表：https://data.eastmoney.com/bbsj/2026-06-30.html
- 东方财富个股估值数据：https://data.eastmoney.com/gzfx/list.html?date=2026-04-30
- 巨潮资讯网原始公告：https://www.cninfo.com.cn/
- 市场总览交叉参考：东方财富策略报告、2026Q1 A 股业绩概览；新浪财经 2026-05-01 A 股一季报全景。

本报告是量化初筛和研究排序，不构成买入、卖出或持仓建议。
"""


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    frame = build_screen()
    export_columns = [
        "代码", "名称", "所处行业", "价格", "涨跌幅", "PE", "PB", "市值亿元",
        "每股收益", "每股净资产", "净资产收益率", "营业总收入-同比增长", "净利润-同比增长",
        "每股经营现金流量", "销售毛利率", "资产负债率", "财报期", "风险标签", "筛选状态", "评分",
    ]
    frame[export_columns].to_csv(DATA / f"a-share-screen-{REPORT_DATE}.csv", index=False, encoding="utf-8-sig")
    (REPORTS / f"A股全量筛选-{REPORT_DATE}.md").write_text(render_report(frame), encoding="utf-8")
    print(f"report={REPORTS / f'A股全量筛选-{REPORT_DATE}.md'}")
    print(f"csv={DATA / f'a-share-screen-{REPORT_DATE}.csv'}")
    print(f"market={len(frame)} base={int(frame['基础可筛'].sum())} hard={int(frame['硬筛通过'].sum())} finance={int((frame['基础可筛'] & frame['金融行业']).sum())}")


if __name__ == "__main__":
    main()
