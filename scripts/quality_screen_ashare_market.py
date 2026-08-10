#!/usr/bin/env python3
"""Fetch and calculate the quality-screen metrics for the local A-share pool.

The repository's 100-company recall pool is used as the reproducible market
representative universe.  This script keeps raw Eastmoney responses beside
the derived metrics so a later report can be audited without re-querying first.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POOL_FILE = ROOT / "筛选公司" / "A股召回池" / "README.md"
DEFAULT_OUTPUT = ROOT / "data" / "A股市场" / "quality-screen-20260803.json"
MAIN_URL = "https://datacenter.eastmoney.com/securities/api/data/get"
CASHFLOW_URL = "https://emweb.eastmoney.com/NewFinanceAnalysis/xjllbAjaxNew"
YEARS_10 = list(range(2016, 2026))
YEARS_5 = list(range(2021, 2026))


def request_json(url: str, params: dict[str, str]) -> dict:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "Mozilla/5.0 quality-screen/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8-sig", "ignore")
    return json.loads(body)


def decimal(value) -> Decimal | None:
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def number(value: Decimal | None):
    if value is None:
        return None
    return float(value.quantize(Decimal("0.000001")))


def average(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal("0")) / Decimal(len(values)) if values else None


def parse_pool() -> list[dict[str, str]]:
    current_category = "未分类"
    companies = []
    row_pattern = re.compile(r"^\|\s*\d+\s*\|\s*(.+?)\s*\|\s*([0-9]{6}\.[A-Z]{2})\s*\|")
    with POOL_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("### "):
                current_category = line[4:].strip()
                continue
            match = row_pattern.match(line.strip())
            if match:
                name, code = match.groups()
                companies.append({"name": name, "code": code, "category": current_category})
    if len(companies) != 100:
        raise RuntimeError(f"候选池解析数量异常：{len(companies)}，预期 100")
    return companies


def main_rows(code: str) -> list[dict]:
    params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA",
        "sty": "ALL",
        "filter": f'(SECUCODE="{code}")(REPORT_TYPE="年报")',
        "p": "1",
        "ps": "20",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
    }
    result = request_json(MAIN_URL, params).get("result") or {}
    return result.get("data") or []


def cashflow_rows(code: str) -> list[dict]:
    numeric, market = code.split(".")
    eastmoney_code = f"{market}{numeric}"
    rows = []
    for batch in (range(2021, 2026), range(2016, 2021)):
        dates = ",".join(f"{year}-12-31 00:00:00" for year in reversed(list(batch)))
        params = {
            "companyType": "4",
            "reportDateType": "0",
            "reportType": "1",
            "dates": dates,
            "code": eastmoney_code,
        }
        response = request_json(CASHFLOW_URL, params)
        rows.extend(response.get("data") or [])
    return rows


def by_year(rows: list[dict]) -> dict[int, dict]:
    result = {}
    for row in rows:
        year_text = str(row.get("REPORT_DATE", ""))[:4]
        if year_text.isdigit():
            result[int(year_text)] = row
    return result


def calculate(company: dict[str, str], main: list[dict], cashflow: list[dict]) -> dict:
    main_year = by_year(main)
    cash_year = by_year(cashflow)
    years_10 = [year for year in YEARS_10 if year in main_year]
    years_5 = [year for year in YEARS_5 if year in main_year and year in cash_year]

    roe_values = [decimal(main_year[year].get("ROEJQ")) for year in years_10]
    gm_values = [decimal(main_year[year].get("XSMLL")) for year in years_5]
    margin_values = [decimal(main_year[year].get("XSJLL")) for year in years_10]
    roe_values = [value for value in roe_values if value is not None]
    gm_values = [value for value in gm_values if value is not None]
    margin_values = [value for value in margin_values if value is not None]

    fcf_by_year = {}
    ocf_ni_by_year = {}
    for year in years_5:
        cash = cash_year[year]
        profit = decimal(main_year[year].get("PARENTNETPROFIT"))
        ocf = decimal(cash.get("NETCASH_OPERATE"))
        capex = decimal(cash.get("CONSTRUCT_LONG_ASSET"))
        if ocf is not None and capex is not None:
            fcf_by_year[str(year)] = number(ocf - capex)
        if ocf is not None and profit not in (None, Decimal("0")):
            ocf_ni_by_year[str(year)] = number(ocf / profit)

    shares = {}
    for year in (2020, 2025):
        row = main_year.get(year)
        if row:
            value = decimal(row.get("TOTAL_SHARE")) or decimal(row.get("A_FREE_SHARE"))
            if value is not None:
                shares[str(year)] = value

    latest = main_year.get(2025) or main_year.get(max(main_year)) if main_year else {}
    latest_roe = decimal(latest.get("ROEJQ")) if latest else None
    latest_cash = cash_year.get(2025) or cash_year.get(max(cash_year)) if cash_year else {}
    latest_ebit = decimal(latest.get("OPERATE_PROFIT_PK")) if latest else None
    latest_finance_expense = decimal(latest_cash.get("FINANCE_EXPENSE")) if latest_cash else None
    if latest_ebit is not None and latest_finance_expense is not None and latest_finance_expense > 0:
        latest_coverage = latest_ebit / latest_finance_expense
        coverage_note = "经营利润/财务费用代理"
    elif latest_finance_expense is not None and latest_finance_expense <= 0:
        latest_coverage = None
        coverage_note = "无净财务费用"
    else:
        latest_coverage = decimal(latest.get("INTEREST_COVERAGE_RATIO")) if latest else None
        coverage_note = "东方财富利息覆盖字段"
    latest_margin = decimal(latest.get("XSJLL")) if latest else None
    latest_gm = decimal(latest.get("XSMLL")) if latest else None
    recent_ocf_positive = all(
        year in cash_year
        and decimal(cash_year[year].get("NETCASH_OPERATE")) is not None
        and decimal(cash_year[year].get("NETCASH_OPERATE")) > 0
        for year in (2024, 2025)
    )
    two_year_margins = [
        decimal(main_year[year].get("XSJLL"))
        for year in (2024, 2025)
        if year in main_year and decimal(main_year[year].get("XSJLL")) is not None
    ]

    values = {
        "roe_avg_10": number(average(roe_values)),
        "fcf_5_total": number(sum((Decimal(str(value)) for value in fcf_by_year.values()), Decimal("0")))
        if len(fcf_by_year) == len(years_5) and years_5
        else None,
        "interest_coverage_latest": number(latest_coverage),
        "gross_margin_avg_5": number(average(gm_values)),
        "ocf_ni_avg_5": number(average([Decimal(str(value)) for value in ocf_ni_by_year.values()])),
        "net_margin_avg_10": number(average(margin_values)),
        "share_inflation_5": number(shares["2025"] / shares["2020"] - Decimal("1"))
        if "2020" in shares and "2025" in shares and shares["2020"]
        else None,
        "interest_coverage_basis": coverage_note,
    }

    checks = {}
    checks["roe"] = None if values["roe_avg_10"] is None else values["roe_avg_10"] >= 8
    checks["fcf"] = None if values["fcf_5_total"] is None else values["fcf_5_total"] >= 0
    checks["interest_coverage"] = (
        "N/A金融" if company["category"].startswith("06 金融") else
        "无净财务费用" if coverage_note == "无净财务费用" else
        None if values["interest_coverage_latest"] is None else values["interest_coverage_latest"] >= 2
    )
    checks["gross_margin"] = (
        "特殊口径" if company["category"].startswith("06 金融") else
        None if values["gross_margin_avg_5"] is None else values["gross_margin_avg_5"] >= 15
    )
    checks["ocf_ni"] = (
        "特殊口径" if company["category"].startswith("06 金融") else
        None if values["ocf_ni_avg_5"] is None else values["ocf_ni_avg_5"] >= 0.7
    )
    checks["net_margin"] = (
        "特殊口径" if company["category"].startswith("06 金融") else
        None if values["net_margin_avg_10"] is None else values["net_margin_avg_10"] >= 5
    )
    checks["share_inflation"] = None if values["share_inflation_5"] is None else values["share_inflation_5"] <= 0.2

    strategic_exemption = (
        len(years_10) < 10
        and latest_gm is not None
        and latest_gm > 30
        and recent_ocf_positive
    )
    margin_exemption = (
        latest_gm is not None
        and latest_gm > 30
        and len(two_year_margins) == 2
        and (all(value >= 5 for value in two_year_margins) or two_year_margins[1] > two_year_margins[0])
    )

    hard_fail_keys = [key for key, value in checks.items() if value is False]
    missing_keys = [key for key, value in checks.items() if value is None]
    is_financial = company["category"].startswith("06 金融")
    if is_financial:
        result = "金融特殊口径"
    elif not missing_keys and not hard_fail_keys:
        result = "通过"
    elif hard_fail_keys == ["roe"] and strategic_exemption:
        result = "豁免A通过"
    elif hard_fail_keys == ["net_margin"] and margin_exemption:
        result = "豁免B通过"
    elif hard_fail_keys:
        result = "排除"
    else:
        result = "数据不足"

    return {
        **company,
        "result": result,
        "financial_window_years": years_10,
        "cashflow_window_years": years_5,
        "values": values,
        "checks": checks,
        "exemptions": {
            "strategic_A_candidate": strategic_exemption,
            "margin_B_candidate": margin_exemption,
            "high_turnover_C_manual_review": False,
        },
        "raw_main": main,
        "raw_cashflow": cashflow,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.08)
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists() and not args.force:
        raise FileExistsError(f"输出已存在，使用 --force 才允许覆盖：{output}")

    companies = parse_pool()
    records = []
    for index, company in enumerate(companies, start=1):
        print(f"[{index:03d}/{len(companies)}] {company['name']} {company['code']}", flush=True)
        errors = []
        try:
            main = main_rows(company["code"])
        except Exception as exc:  # keep the batch auditable if one endpoint fails
            main = []
            errors.append(f"main: {type(exc).__name__}: {exc}")
        time.sleep(args.sleep)
        try:
            cashflow = cashflow_rows(company["code"])
        except Exception as exc:
            cashflow = []
            errors.append(f"cashflow: {type(exc).__name__}: {exc}")
        record = calculate(company, main, cashflow)
        record["errors"] = errors
        records.append(record)
        time.sleep(args.sleep)

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": "2026-08-03",
        "universe": "筛选公司/A股召回池/README.md 的 100 家代表性候选公司",
        "financial_cutoff": "2025-12-31",
        "sources": {
            "main_financials": MAIN_URL,
            "cashflow": CASHFLOW_URL,
            "candidate_pool": str(POOL_FILE.relative_to(ROOT)),
        },
        "records": records,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入：{output}")


if __name__ == "__main__":
    run()
