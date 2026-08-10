#!/usr/bin/env python3
"""Run the seven-metric quality screen on all current A-share stocks.

The default mode removes financial and explicitly cyclical industries before
the quality screen.  ``--include-financial-cyclical`` keeps the same market
universe but calculates every company, marking the financial metrics that are
not comparable to ordinary industrial companies.  The batch sources are
public Eastmoney endpoints; derived values are calculated with Decimal and
the output keeps source-year coverage per stock.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AS_OF = date.today().strftime("%Y%m%d")
DEFAULT_DATA = ROOT / "data" / "A股市场" / f"quality-screen-ashare-excluding-financial-cyclical-{DEFAULT_AS_OF}.json"
DEFAULT_CSV = ROOT / "data" / "A股市场" / f"quality-screen-ashare-excluding-financial-cyclical-{DEFAULT_AS_OF}.csv"
DEFAULT_REPORT = ROOT / "reports" / "A股市场" / f"quality-screen-ashare-excluding-financial-cyclical-{DEFAULT_AS_OF}.md"

MARKET_URL = "https://push2.eastmoney.com/api/qt/clist/get"
F10_URL = "https://datacenter.eastmoney.com/securities/api/data/get"
STATEMENT_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
MARKET_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
PAGE_SIZE_MARKET = 100
PAGE_SIZE_STATEMENT = 500
PAGE_SIZE_F10 = 5000
YEARS_10 = list(range(2016, 2026))
YEARS_5 = list(range(2021, 2026))

# These are deliberately explicit so the scope can be reviewed and adjusted.
FINANCIAL_RE = re.compile(r"银行|保险|证券|多元金融|金融")
CYCLICAL_RE = re.compile(
    r"煤炭|石油|采掘|钢铁|工业金属|有色金属|贵金属|小金属|能源金属|"
    r"化学原料|化学制品|化肥|农药|橡胶制品|塑料制品|水泥|玻璃玻纤|"
    r"建筑材料|建筑装饰|基础建设|专业工程|房地产|航运港口|航空机场|铁路公路|"
    r"汽车整车|汽车零部件|汽车服务|工程机械"
)


def request_json(url: str, params: dict[str, str], *, timeout: int = 90, retries: int = 5) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0 quality-screen-ashare/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8-sig", "ignore"))
        except Exception as error:  # keep a batch retryable without hiding failures
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}: {last_error}") from last_error


def decimal(value: object) -> Decimal | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def number(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001")))


def average(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal("0")) / Decimal(len(values)) if values else None


def exchange_for(code: str, market_id: object) -> str:
    if str(market_id) == "1" or code.startswith("6"):
        return "SH"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def fetch_market() -> list[dict[str, str]]:
    try:
        import akshare as ak

        frame = ak.stock_zh_a_spot()
        by_code: dict[str, dict[str, str]] = {}
        for row in frame.to_dict("records"):
            raw_code = str(row.get("代码") or "")
            match = re.search(r"(\d{6})$", raw_code)
            code = match.group(1) if match else ""
            if re.fullmatch(r"\d{6}", code):
                by_code[code] = {
                    "code": code,
                    "name": str(row.get("名称") or "").strip(),
                    "exchange": exchange_for(code, None),
                    "industry": "",
                }
        if by_code:
            return sorted(by_code.values(), key=lambda item: item["code"])
    except Exception as error:
        print(f"akshare market fallback: {type(error).__name__}: {error}", flush=True)

    first = request_json(
        MARKET_URL,
        {
            "pn": "1",
            "pz": str(PAGE_SIZE_MARKET),
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": MARKET_FS,
            "fields": "f12,f14,f13,f100",
        },
    )
    data = first.get("data") or {}
    total = int(data.get("total") or 0)
    pages = max(1, math.ceil(total / PAGE_SIZE_MARKET))
    rows = list(data.get("diff") or [])
    for page in range(2, pages + 1):
        time.sleep(0.25)
        response = request_json(
            MARKET_URL,
            {
                "pn": str(page),
                "pz": str(PAGE_SIZE_MARKET),
                "po": "1",
                "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": MARKET_FS,
                "fields": "f12,f14,f13,f100",
            },
        )
        rows.extend((response.get("data") or {}).get("diff") or [])
        print(f"market page {page}/{pages}", flush=True)

    by_code: dict[str, dict[str, str]] = {}
    for row in rows:
        code = str(row.get("f12") or "").zfill(6)
        if not re.fullmatch(r"\d{6}", code):
            continue
        by_code[code] = {
            "code": code,
            "name": str(row.get("f14") or "").strip(),
            "exchange": exchange_for(code, row.get("f13")),
            "industry": str(row.get("f100") or "").strip(),
        }
    return sorted(by_code.values(), key=lambda item: item["code"])


def fetch_statement(report_name: str, report_date: str, columns: str) -> list[dict]:
    first = request_json(
        STATEMENT_URL,
        {
            "sortColumns": "SECURITY_CODE",
            "sortTypes": "1",
            "pageSize": str(PAGE_SIZE_STATEMENT),
            "pageNumber": "1",
            "reportName": report_name,
            "columns": columns,
            "filter": f"(REPORT_DATE='{report_date} 00:00:00')",
        },
    )
    result = first.get("result") or {}
    total = int(result.get("count") or 0)
    pages = max(1, math.ceil(total / PAGE_SIZE_STATEMENT))
    rows = list(result.get("data") or [])
    for page in range(2, pages + 1):
        response = request_json(
            STATEMENT_URL,
            {
                "sortColumns": "SECURITY_CODE",
                "sortTypes": "1",
                "pageSize": str(PAGE_SIZE_STATEMENT),
                "pageNumber": str(page),
                "reportName": report_name,
                "columns": columns,
                "filter": f"(REPORT_DATE='{report_date} 00:00:00')",
            },
        )
        rows.extend((response.get("result") or {}).get("data") or [])
    return rows


def fetch_quality_rows() -> list[dict]:
    """Fetch all annual ROE/gross-margin rows in one paginated batch."""
    params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA",
        "sty": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,REPORT_YEAR,ROEJQ,XSMLL",
        "filter": '(REPORT_TYPE="年报")(REPORT_YEAR>=2016)(REPORT_YEAR<=2025)',
        "p": "1",
        "ps": str(PAGE_SIZE_F10),
        "sr": "1",
        "st": "SECURITY_CODE",
        "source": "HSF10",
        "client": "PC",
    }
    first = request_json(F10_URL, params, timeout=120)
    result = first.get("result") or {}
    pages = int(result.get("pages") or 0)
    rows = list(result.get("data") or [])
    for page in range(2, pages + 1):
        page_params = dict(params)
        page_params["p"] = str(page)
        response = request_json(F10_URL, page_params, timeout=120)
        rows.extend((response.get("result") or {}).get("data") or [])
        print(f"quality rows page {page}/{pages}", flush=True)
    return rows


def fetch_share_rows(year: int) -> list[dict]:
    params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA",
        "sty": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,REPORT_YEAR,TOTAL_SHARE",
        "filter": f"(REPORT_YEAR={year})",
        "p": "1",
        "ps": str(PAGE_SIZE_F10),
        "sr": "1",
        "st": "SECURITY_CODE",
        "source": "HSF10",
        "client": "PC",
    }
    first = request_json(F10_URL, params, timeout=120)
    result = first.get("result") or {}
    pages = int(result.get("pages") or 0)
    rows = list(result.get("data") or [])
    for page in range(2, pages + 1):
        page_params = dict(params)
        page_params["p"] = str(page)
        response = request_json(F10_URL, page_params, timeout=120)
        rows.extend((response.get("result") or {}).get("data") or [])
        print(f"share {year} page {page}/{pages}", flush=True)
    return rows


def index_rows(rows: list[dict], year_key: str) -> dict[str, dict[int, dict]]:
    indexed: dict[str, dict[int, dict]] = defaultdict(dict)
    for row in rows:
        code = str(row.get("SECURITY_CODE") or "").zfill(6)
        year_value = row.get(year_key)
        if not code or year_value in (None, ""):
            continue
        try:
            year = int(str(year_value)[:4])
        except ValueError:
            continue
        indexed[code][year] = row
    return indexed


def classify(industry: str) -> tuple[str, str]:
    if FINANCIAL_RE.search(industry):
        return "金融", "金融行业"
    if CYCLICAL_RE.search(industry):
        return "周期", "周期性行业"
    return "保留", ""


def calculate(
    company: dict,
    quality: dict[int, dict],
    income: dict[int, dict],
    cash: dict[int, dict],
    shares: dict[int, dict],
    *,
    financial_special: bool = False,
) -> dict:
    years_10 = [year for year in YEARS_10 if year in quality and year in income]
    years_5 = [year for year in YEARS_5 if year in income and year in cash]
    roe_years = [year for year in YEARS_10 if year in quality]
    gm_years = [year for year in YEARS_5 if year in quality]
    margin_years = [year for year in YEARS_10 if year in income]

    roe_values = [decimal(quality[year].get("ROEJQ")) for year in roe_years]
    gm_values = [decimal(quality[year].get("XSMLL")) for year in gm_years]
    net_margin_values: list[Decimal] = []
    for year in margin_years:
        revenue = decimal(income[year].get("TOTAL_OPERATE_INCOME"))
        profit = decimal(income[year].get("PARENT_NETPROFIT"))
        if revenue not in (None, Decimal("0")) and profit is not None:
            net_margin_values.append(profit / revenue * Decimal("100"))
    roe_values = [value for value in roe_values if value is not None]
    gm_values = [value for value in gm_values if value is not None]

    fcf_by_year: dict[str, float] = {}
    ocf_ni_by_year: dict[str, float] = {}
    for year in years_5:
        ocf = decimal(cash[year].get("NETCASH_OPERATE"))
        capex = decimal(cash[year].get("CONSTRUCT_LONG_ASSET"))
        profit = decimal(income[year].get("PARENT_NETPROFIT"))
        if ocf is not None and capex is not None:
            fcf_by_year[str(year)] = number(ocf - capex) or 0.0
        if ocf is not None and profit not in (None, Decimal("0")):
            ocf_ni_by_year[str(year)] = number(ocf / profit) or 0.0

    latest_income = income.get(2025) or income.get(max(income)) if income else {}
    latest_quality = quality.get(2025) or quality.get(max(quality)) if quality else {}
    latest_finance = decimal(latest_income.get("FINANCE_EXPENSE")) if latest_income else None
    latest_operate_profit = decimal(latest_income.get("OPERATE_PROFIT")) if latest_income else None
    if latest_finance is not None and latest_finance > 0 and latest_operate_profit is not None:
        coverage = latest_operate_profit / latest_finance
        coverage_basis = "经营利润/财务费用代理"
    elif latest_finance is not None and latest_finance <= 0:
        coverage = None
        coverage_basis = "无净财务费用"
    else:
        coverage = None
        coverage_basis = "数据不足"

    share_2020 = decimal((shares.get(2020) or {}).get("TOTAL_SHARE"))
    share_2025 = decimal((shares.get(2025) or {}).get("TOTAL_SHARE"))
    values = {
        "roe_avg_10": number(average(roe_values)),
        "fcf_5_total": number(sum((Decimal(str(value)) for value in fcf_by_year.values()), Decimal("0"))) if len(fcf_by_year) == 5 else None,
        "interest_coverage_latest": number(coverage),
        "gross_margin_avg_5": number(average(gm_values)) if len(gm_values) == 5 else None,
        "ocf_ni_avg_5": number(average([Decimal(str(value)) for value in ocf_ni_by_year.values()])) if len(ocf_ni_by_year) == 5 else None,
        "net_margin_avg_10": number(average(net_margin_values)) if len(net_margin_values) == 10 else None,
        "share_inflation_5": number(share_2025 / share_2020 - Decimal("1")) if share_2020 not in (None, Decimal("0")) and share_2025 is not None else None,
        "interest_coverage_basis": coverage_basis,
    }
    checks = {
        "roe": None if values["roe_avg_10"] is None else values["roe_avg_10"] >= 8,
        "fcf": None if values["fcf_5_total"] is None else values["fcf_5_total"] >= 0,
        "interest_coverage": "无净财务费用" if coverage_basis == "无净财务费用" else None if values["interest_coverage_latest"] is None else values["interest_coverage_latest"] >= 2,
        "gross_margin": None if values["gross_margin_avg_5"] is None else values["gross_margin_avg_5"] >= 15,
        "ocf_ni": None if values["ocf_ni_avg_5"] is None else values["ocf_ni_avg_5"] >= 0.7,
        "net_margin": None if values["net_margin_avg_10"] is None else values["net_margin_avg_10"] >= 5,
        "share_inflation": None if values["share_inflation_5"] is None else values["share_inflation_5"] <= 0.2,
    }
    if financial_special:
        checks.update({
            "interest_coverage": "金融特殊口径",
            "gross_margin": "金融特殊口径",
            "ocf_ni": "金融特殊口径",
            "net_margin": "金融特殊口径",
        })
    latest_gm = decimal(latest_quality.get("XSMLL")) if latest_quality else None
    recent_ocf_positive = all(
        year in cash and decimal(cash[year].get("NETCASH_OPERATE")) is not None and decimal(cash[year].get("NETCASH_OPERATE")) > 0
        for year in (2024, 2025)
    )
    latest_two_margins = []
    for year in (2024, 2025):
        revenue = decimal((income.get(year) or {}).get("TOTAL_OPERATE_INCOME"))
        profit = decimal((income.get(year) or {}).get("PARENT_NETPROFIT"))
        if revenue not in (None, Decimal("0")) and profit is not None:
            latest_two_margins.append(profit / revenue * Decimal("100"))
    strategic_a = len(years_10) < 10 and latest_gm is not None and latest_gm > 30 and recent_ocf_positive
    margin_b = latest_gm is not None and latest_gm > 30 and len(latest_two_margins) == 2 and (
        all(value >= 5 for value in latest_two_margins) or latest_two_margins[1] > latest_two_margins[0]
    )
    failed = [key for key, value in checks.items() if value is False]
    missing = [key for key, value in checks.items() if value is None]
    financial_required = {"roe", "fcf", "share_inflation"}
    if financial_special and any(key in failed for key in financial_required):
        result = "金融特殊口径排除"
    elif financial_special and any(key in missing for key in financial_required):
        result = "金融数据不足"
    elif financial_special:
        result = "金融特殊口径通过"
    elif not missing and not failed:
        result = "通过"
    elif failed == ["roe"] and strategic_a:
        result = "豁免A通过"
    elif failed == ["net_margin"] and margin_b:
        result = "豁免B通过"
    elif failed:
        result = "排除"
    else:
        result = "数据不足"
    return {
        "financial_window_years": years_10,
        "cashflow_window_years": years_5,
        "values": values,
        "checks": checks,
        "missing_fields": missing,
        "failed_fields": failed,
        "exemptions": {
            "strategic_A_candidate": strategic_a,
            "margin_B_candidate": margin_b,
            "high_turnover_C_manual_review": False,
        },
        "result": result,
    }


def pct(value: object) -> str:
    return "数据不足" if value is None else f"{float(value):.2f}%"


def ratio(value: object) -> str:
    return "数据不足" if value is None else f"{float(value):.2f}"


def fcf_value(value: object) -> str:
    return "数据不足" if value is None else f"{float(value) / 100_000_000:.1f}亿"


def render_report(payload: dict) -> str:
    records = payload["records"]
    full_market = bool(payload.get("include_financial_cyclical"))
    included = records if full_market else [row for row in records if row["scope"] == "保留"]
    passed_results = {"通过", "豁免A通过", "豁免B通过", "金融特殊口径通过"}
    excluded_results = {"排除", "金融特殊口径排除"}
    insufficient_results = {"数据不足", "金融数据不足"}
    passed = [row for row in included if row["result"] in passed_results]
    excluded = [row for row in included if row["result"] in excluded_results]
    insufficient = [row for row in included if row["result"] in insufficient_results]
    early = [row for row in records if row["scope"] != "保留"]
    early_counts = Counter(row["scope_reason"] for row in early)
    fail_counts = Counter(key for row in excluded for key in row["failed_fields"])
    industry_stats = []
    for industry in sorted({row["industry"] or "未分类" for row in included}):
        rows = [row for row in included if (row["industry"] or "未分类") == industry]
        passed_count = sum(row["result"] in passed_results for row in rows)
        industry_stats.append((industry, len(rows), passed_count, f"{passed_count / len(rows):.1%}" if rows else "--"))
    industry_stats.sort(key=lambda item: (-item[2], -item[1], item[0]))
    quality_order = {"通过": 0, "金融特殊口径通过": 1, "豁免A通过": 2, "豁免B通过": 3, "数据不足": 4, "金融数据不足": 5, "排除": 6, "金融特殊口径排除": 7}
    sorted_passed = sorted(passed, key=lambda row: row["values"].get("roe_avg_10") or -999, reverse=True)
    financial_count = sum(row.get("original_scope") == "金融" for row in records)
    cyclical_count = sum(row.get("original_scope") == "周期" for row in records)
    retained_count = len(records) - financial_count - cyclical_count
    if full_market:
        conclusion = f"母池 {len(records)} 家；其中金融 {financial_count} 家、周期 {cyclical_count} 家、其他行业 {retained_count} 家全部纳入计算。普通口径通过/豁免 {len(passed) - sum(row['result'] == '金融特殊口径通过' for row in passed)} 家，金融特殊口径通过 {sum(row['result'] == '金融特殊口径通过' for row in passed)} 家，明确排除 {len(excluded)} 家，数据不足 {len(insufficient)} 家。"
        scope_line = "> 市场范围：东方财富沪深京 A 股行情母池；本次包含金融与明确列出的周期性行业，金融公司按特殊口径标记，不提前排除。"
        title = "# A股全市场质量筛选（包含金融与周期行业）"
        scope_note = "金融与周期行业均纳入计算；金融公司中利息覆盖、毛利率、经营现金流/净利和净利率标记为金融特殊口径，不与普通行业横向比较。"
        result_heading = "## 全市场结果"
        result_intro = "| 公司 | 代码 | 行业 | 原始分类 | ROE均值 | 5年FCF | 利息覆盖 | 毛利率 | OCF/净利 | 净利率 | 股本膨胀 | 缺失/失败 | 结果 |"
        result_separator = "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"
    else:
        conclusion = f"母池 {len(records)} 家，提前剔除金融 {early_counts.get('金融行业', 0)} 家、周期性行业 {early_counts.get('周期性行业', 0)} 家；保留其他行业 {len(included)} 家。保留池中七项全部通过或触发豁免 {len(passed)} 家，明确排除 {len(excluded)} 家，数据不足 {len(insufficient)} 家。"
        scope_line = "> 市场范围：AkShare/Sina 返回的沪深京 A 股行情母池；金融与明确列出的周期性行业在七指标计算前剔除。"
        title = "# A股去金融与周期行业后的质量筛选"
        scope_note = "提前剔除不是公司质量判断，而是按用户指定的行业边界处理；周期分类采用脚本中的公开、可审阅关键词，混合业务公司应在个股研究中复核。"
        result_heading = "## 保留池全量结果"
        result_intro = "| 公司 | 代码 | 行业 | ROE均值 | 5年FCF | 利息覆盖 | 毛利率 | OCF/净利 | 净利率 | 股本膨胀 | 缺失/失败 | 结果 |"
        result_separator = "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"
    lines = [
        title,
        "",
        f"> 筛选日期：{payload['as_of']}  ",
        "> 财务数据截止：2025-12-31  ",
        scope_line,
        "> 研究性质：质量初筛，不包含当前估值、买入价和持仓建议。",
        "",
        "## 结论",
        "",
        conclusion,
        "",
        scope_note,
        "",
        "## 七项口径",
        "",
        "| 指标 | 计算窗口 | 排除阈值 |",
        "|---|---|---:|",
        "| ①平均 ROE | 2016–2025 年年度 ROE 均值；不足窗口不自动通过 | < 8% |",
        "| ②累计 FCF | 2021–2025 年经营现金流 - 长期资产购建现金 | < 0 |",
        "| ③利息覆盖 | 最新年度经营利润 / 财务费用代理；净财务费用≤0单列 | < 2 倍 |",
        "| ④平均毛利率 | 2021–2025 年均值 | < 15% |",
        "| ⑤平均 OCF/净利 | 2021–2025 年逐年比值均值 | < 0.7 |",
        "| ⑥平均净利率 | 2016–2025 年归母净利 / 营业收入均值 | < 5% |",
        "| ⑦股本膨胀 | 2025 年总股本 / 2020 年总股本 - 1 | > 20% |",
        "",
        "金融分类关键词：银行、保险、证券、多元金融、金融。周期分类关键词：煤炭、石油、采掘、钢铁、有色金属、金属、化工、建材、地产、基建、航运、机场、铁路公路、汽车、工程机械等；分类不再用于全市场模式的提前剔除。",
        "",
        "## 行业统计",
        "",
        f"| 行业 | {'样本' if full_market else '保留样本'} | 通过/豁免 | 通过率 |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(f"| {industry} | {total} | {passed_count} | {rate} |" for industry, total, passed_count, rate in industry_stats)
    lines += [
        "",
        "## 通过与豁免公司",
        "",
        ", ".join(f"{row['name']}（{row['code']}）" for row in sorted_passed) or "无",
        "",
        "## 排除指标杀伤力",
        "",
        "| 指标 | 已知不通过次数 |",
        "|---|---:|",
    ]
    labels = {"roe": "ROE", "fcf": "FCF", "interest_coverage": "利息覆盖", "gross_margin": "毛利率", "ocf_ni": "OCF/净利", "net_margin": "净利率", "share_inflation": "股本膨胀"}
    lines.extend(f"| {labels[key]} | {fail_counts.get(key, 0)} |" for key in labels)
    lines += [
        "",
        result_heading,
        "",
        result_intro,
        result_separator,
    ]
    for row in sorted(included, key=lambda item: (quality_order.get(item["result"], 9), -(item["values"].get("roe_avg_10") or -999), item["code"])):
        values = row["values"]
        checks = "、".join(labels.get(key, key) for key in row["missing_fields"] + row["failed_fields"]) or "-"
        interest = "金融特殊口径" if row.get("original_scope") == "金融" else ratio(values.get("interest_coverage_latest"))
        gross_margin = "金融特殊口径" if row.get("original_scope") == "金融" else pct(values.get("gross_margin_avg_5"))
        ocf_ni = "金融特殊口径" if row.get("original_scope") == "金融" else ratio(values.get("ocf_ni_avg_5"))
        net_margin = "金融特殊口径" if row.get("original_scope") == "金融" else pct(values.get("net_margin_avg_10"))
        original_scope = row.get("original_scope") if full_market else None
        scope_cell = f" | {original_scope}" if full_market else ""
        lines.append(
            f"| {row['name']} | {row['code']} | {row['industry'] or '未分类'}{scope_cell} | {pct(values.get('roe_avg_10'))} | {fcf_value(values.get('fcf_5_total'))} | "
            f"{interest} | {gross_margin} | {ocf_ni} | {net_margin} | {pct((values.get('share_inflation_5') or 0) * 100) if values.get('share_inflation_5') is not None else '数据不足'} | {checks} | **{row['result']}** |"
        )
    lines += [
        "",
        "## 数据边界与审计说明",
        "",
        f"- 东方财富批量行情母池：{payload['source_counts']['market']} 家；财务报表请求均按年度分页，成功返回行数见 JSON。",
        "- 2025 年报是最后一个完整年度；当前行情不参与七项质量判定。",
        "- 批量财务数据来自东方财富的不同公开接口，属于同一供应商的交叉接口，不等于东方财富与巨潮的独立双源逐项审计。重点公司进入深度研究前仍需用巨潮年报复核。",
        "- 上市不足十年的公司使用全部可得年度，但窗口不足会保留在结果中；数据不足绝不自动通过。",
        "- 高周转薄利豁免 C 需要业务性质人工判断，本轮未自动放行。",
        "",
        "## 来源",
        "",
        "- 行情母池：AkShare `stock_zh_a_spot`（底层为新浪财经沪深京 A 股行情）；行业名称由东方财富年报指标接口补齐。",
        "- 年度主要财务指标：https://datacenter.eastmoney.com/securities/api/data/get（RPT_F10_FINANCE_MAINFINADATA）",
        "- 利润表：https://datacenter-web.eastmoney.com/api/data/v1/get（RPT_DMSK_FN_INCOME）",
        "- 现金流量表：https://datacenter-web.eastmoney.com/api/data/v1/get（RPT_DMSK_FN_CASHFLOW）",
        f"- 结果数据：`{payload['data_path']}`；明细 CSV：`{payload['csv_path']}`。",
        "",
        "本报告用于学习和研究，不构成投资建议。",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict, data_path: Path, csv_path: Path, report_path: Path, *, force: bool) -> None:
    for path in (data_path, csv_path, report_path):
        if path.exists() and not force:
            raise FileExistsError(f"输出已存在，使用 --force 才允许覆盖：{path}")
    data_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload["data_path"] = data_path.relative_to(ROOT).as_posix()
    payload["csv_path"] = csv_path.relative_to(ROOT).as_posix()
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fieldnames = ["code", "name", "exchange", "industry", "scope", "scope_reason", "original_scope", "original_scope_reason", "result", "roe_avg_10", "fcf_5_total", "interest_coverage_latest", "gross_margin_avg_5", "ocf_ni_avg_5", "net_margin_avg_10", "share_inflation_5", "missing_fields", "failed_fields", "financial_window_years", "cashflow_window_years"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in payload["records"]:
            values = row.get("values", {})
            writer.writerow({
                "code": row["code"], "name": row["name"], "exchange": row["exchange"], "industry": row["industry"], "scope": row["scope"], "scope_reason": row["scope_reason"], "original_scope": row.get("original_scope", row["scope"]), "original_scope_reason": row.get("original_scope_reason", row["scope_reason"]), "result": row.get("result", "行业排除"),
                "roe_avg_10": values.get("roe_avg_10"), "fcf_5_total": values.get("fcf_5_total"), "interest_coverage_latest": values.get("interest_coverage_latest"), "gross_margin_avg_5": values.get("gross_margin_avg_5"), "ocf_ni_avg_5": values.get("ocf_ni_avg_5"), "net_margin_avg_10": values.get("net_margin_avg_10"), "share_inflation_5": values.get("share_inflation_5"),
                "missing_fields": ",".join(row.get("missing_fields", [])), "failed_fields": ",".join(row.get("failed_fields", [])), "financial_window_years": ",".join(map(str, row.get("financial_window_years", []))), "cashflow_window_years": ",".join(map(str, row.get("cashflow_window_years", []))),
            })
    report_path.write_text(render_report(payload), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument("--include-financial-cyclical", action="store_true", help="纳入金融与周期行业；金融的四项不可比指标标记为特殊口径")
    parser.add_argument("--data", type=Path, default=None)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    filename_prefix = "quality-screen-ashare-all" if args.include_financial_cyclical else "quality-screen-ashare-excluding-financial-cyclical"
    data_path = args.data or ROOT / "data" / "A股市场" / f"{filename_prefix}-{args.as_of}.json"
    csv_path = args.csv or ROOT / "data" / "A股市场" / f"{filename_prefix}-{args.as_of}.csv"
    report_path = args.report or ROOT / "reports" / "A股市场" / f"{filename_prefix}-{args.as_of}.md"
    data_path = data_path if data_path.is_absolute() else ROOT / data_path
    csv_path = csv_path if csv_path.is_absolute() else ROOT / csv_path
    report_path = report_path if report_path.is_absolute() else ROOT / report_path

    market = fetch_market()
    print(f"market rows: {len(market)}", flush=True)
    quality_rows = fetch_quality_rows()
    quality = index_rows(quality_rows, "REPORT_YEAR")
    income_by_year: dict[int, dict[str, dict]] = {}
    cash_by_year: dict[int, dict[str, dict]] = {}
    for year in YEARS_10:
        report_date = f"{year}-12-31"
        income_rows = fetch_statement("RPT_DMSK_FN_INCOME", report_date, "SECURITY_CODE,SECURITY_NAME_ABBR,INDUSTRY_NAME,REPORT_DATE,PARENT_NETPROFIT,TOTAL_OPERATE_INCOME,OPERATE_PROFIT,FINANCE_EXPENSE")
        cash_rows = fetch_statement("RPT_DMSK_FN_CASHFLOW", report_date, "SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,NETCASH_OPERATE,CONSTRUCT_LONG_ASSET")
        income_by_year[year] = {str(row.get("SECURITY_CODE") or "").zfill(6): row for row in income_rows}
        cash_by_year[year] = {str(row.get("SECURITY_CODE") or "").zfill(6): row for row in cash_rows}
        print(f"statements {year}: income={len(income_rows)} cash={len(cash_rows)}", flush=True)
    shares_by_year = {year: index_rows(fetch_share_rows(year), "REPORT_YEAR") for year in (2020, 2025)}
    industry_by_code = {
        code: str(row.get("INDUSTRY_NAME") or "").strip()
        for code, row in income_by_year[2025].items()
        if row.get("INDUSTRY_NAME")
    }

    records = []
    source_counts = {"market": len(market), "quality_rows": len(quality_rows), "income_rows": {}, "cashflow_rows": {}, "share_rows": {}}
    for year in YEARS_10:
        source_counts["income_rows"][str(year)] = len(income_by_year[year])
        source_counts["cashflow_rows"][str(year)] = len(cash_by_year[year])
    for year, rows in shares_by_year.items():
        source_counts["share_rows"][str(year)] = len(rows)

    for company in market:
        code = company["code"]
        industry = company["industry"] or industry_by_code.get(code, "")
        if not industry:
            industry = ""
        classified_scope, classified_reason = classify(industry)
        if args.include_financial_cyclical:
            record = {
                **company,
                "industry": industry,
                "scope": "全市场",
                "scope_reason": "本次包含金融与周期行业",
                "original_scope": classified_scope,
                "original_scope_reason": classified_reason,
            }
            financial_special = classified_scope == "金融"
            income = {year: income_by_year[year][code] for year in YEARS_10 if code in income_by_year[year]}
            cash = {year: cash_by_year[year][code] for year in YEARS_10 if code in cash_by_year[year]}
            quality_code = quality.get(code, {})
            shares = {year: (shares_by_year[year].get(code) or {}).get(year, {}) for year in (2020, 2025)}
            record.update(calculate(company, quality_code, income, cash, shares, financial_special=financial_special))
        else:
            record = {
                **company,
                "industry": industry,
                "scope": classified_scope,
                "scope_reason": classified_reason,
                "original_scope": classified_scope,
                "original_scope_reason": classified_reason,
            }
            if classified_scope == "保留":
                income = {year: income_by_year[year][code] for year in YEARS_10 if code in income_by_year[year]}
                cash = {year: cash_by_year[year][code] for year in YEARS_10 if code in cash_by_year[year]}
                quality_code = quality.get(code, {})
                shares = {year: (shares_by_year[year].get(code) or {}).get(year, {}) for year in (2020, 2025)}
                record.update(calculate(company, quality_code, income, cash, shares))
            else:
                record.update({"result": "行业排除", "financial_window_years": [], "cashflow_window_years": [], "values": {}, "checks": {}, "missing_fields": [], "failed_fields": [], "exemptions": {}})
        records.append(record)

    payload = {
        "as_of": args.as_of,
        "financial_cutoff": "2025-12-31",
        "universe": "东方财富沪深京 A 股行情母池",
        "include_financial_cyclical": args.include_financial_cyclical,
        "scope_rules": {"financial_regex": FINANCIAL_RE.pattern, "cyclical_regex": CYCLICAL_RE.pattern, "market_fs": MARKET_FS},
        "sources": {"market": MARKET_URL, "quality_rows": F10_URL, "income": STATEMENT_URL, "cashflow": STATEMENT_URL, "shares": F10_URL},
        "source_counts": source_counts,
        "records": records,
    }
    write_outputs(payload, data_path, csv_path, report_path, force=args.force)
    summary = Counter(row["result"] for row in records)
    print(json.dumps({"data": str(data_path), "csv": str(csv_path), "report": str(report_path), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
