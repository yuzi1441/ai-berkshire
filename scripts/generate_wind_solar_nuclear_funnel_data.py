#!/usr/bin/env python3
"""Generate the A-share wind, solar and nuclear funnel financial snapshot.

Financial statements come from Eastmoney through AkShare. CNInfo links are
captured alongside each row so the aggregator values can be checked against
the statutory annual and quarterly reports. Quotes come from Tencent.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import akshare as ak
import requests


COMPANIES = [
    ("601985", "中国核电", "核电运营", "核电/新能源运营商"),
    ("003816", "中国广核", "核电运营", "核电运营商"),
    ("600905", "三峡能源", "风光运营", "陆风/海风/光伏运营商"),
    ("300274", "阳光电源", "光伏设备", "逆变器/储能/电站系统"),
    ("002202", "金风科技", "风电整机", "风机整机/风电场服务与运营"),
    ("601615", "明阳智能", "海上风电整机", "大型海风机组/新能源运营"),
    ("603606", "东方电缆", "海上风电海缆", "海缆/陆缆系统"),
    ("002487", "大金重工", "海上风电基础", "海工基础/塔筒出口"),
    ("603806", "福斯特", "光伏材料", "光伏胶膜/背板"),
    ("601012", "隆基绿能", "光伏制造", "硅片/电池/组件"),
    ("600438", "通威股份", "光伏制造", "高纯晶硅/电池片/农牧"),
    ("600875", "东方电气", "发电设备", "核电/风电/火电/水电设备"),
    ("002438", "江苏神通", "核电设备", "核级蝶阀/球阀及冶金阀门"),
    ("301155", "海力风电", "海上风电基础", "海风塔筒/桩基"),
    ("600522", "中天科技", "海上风电海缆", "海缆/光通信/电力传输"),
    ("601016", "节能风电", "风电运营", "陆上风电运营商"),
    ("600483", "福能股份", "海上风电运营", "福建海风/陆风/热电运营"),
]

METRICS = {
    "revenue": "营业总收入",
    "net_profit": "归母净利润",
    "operating_cash_flow": "经营现金流量净额",
    "roe": "净资产收益率(ROE)",
    "gross_margin": "毛利率",
    "debt_asset": "资产负债率",
}


def number(value):
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def metric(frame, label: str, report_date: str):
    matches = frame[frame["指标"].astype(str).eq(label)]
    if matches.empty or report_date not in frame.columns:
        return None
    return number(matches.iloc[0][report_date])


def ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return float(Decimal(str(numerator)) / Decimal(str(denominator)))
    except (InvalidOperation, ZeroDivisionError):
        return None


def market_prefix(code: str) -> str:
    return "SH" if code.startswith(("5", "6", "9")) else "SZ"


def tencent_code(code: str) -> str:
    return ("sh" if market_prefix(code) == "SH" else "sz") + code


def fetch_quotes():
    symbols = ",".join(tencent_code(code) for code, *_ in COMPANIES)
    response = requests.get(
        "https://qt.gtimg.cn/q=" + symbols,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = "gbk"
    quotes = {}
    for record in response.text.split(";"):
        if '="' not in record:
            continue
        fields = record.split('"', 2)[1].split("~")
        if len(fields) <= 46:
            continue
        quotes[fields[2]] = {
            "quote_time": fields[30] or None,
            "price": number(fields[3]),
            "day_change_pct": number(fields[32]),
            "turnover_pct": number(fields[38]),
            "pe_ttm": number(fields[39]),
            "market_cap_yi": number(fields[45]),
            "pb": number(fields[46]),
        }
    return quotes


def clean_title(value: str) -> str:
    return re.sub(r"</?em>", "", str(value))


def find_cninfo_report(code: str, keyword: str, category: str, end_date: str):
    try:
        frame = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=code,
            keyword=keyword,
            category=category,
            start_date="20260101",
            end_date=end_date,
        )
    except Exception as exc:  # Keep the snapshot usable when CNInfo throttles.
        return {"error": f"{type(exc).__name__}: {exc}"}

    for _, item in frame.iterrows():
        title = clean_title(item.get("公告标题", ""))
        if "摘要" in title or "取消" in title:
            continue
        detail_url = str(item.get("公告链接", ""))
        published = str(item.get("公告时间", ""))[:10]
        query = parse_qs(urlparse(detail_url).query)
        announcement_id = (query.get("announcementId") or [None])[0]
        pdf_url = None
        if announcement_id and published:
            pdf_url = (
                f"https://static.cninfo.com.cn/finalpage/{published}/"
                f"{announcement_id}.PDF"
            )
        return {
            "title": title,
            "published_date": published,
            "detail_url": detail_url,
            "pdf_url": pdf_url,
        }
    return {"error": "not found"}


def build_row(code, name, subsector, business, quotes, end_date):
    frame = ak.stock_financial_abstract(code)
    row = {
        "code": code,
        "market": market_prefix(code),
        "name": name,
        "subsector": subsector,
        "business": business,
        **quotes.get(code, {}),
    }

    for report_date, label in [
        ("20231231", "2023"),
        ("20241231", "2024"),
        ("20251231", "2025"),
        ("20250331", "2025Q1"),
        ("20260331", "2026Q1"),
    ]:
        for key, source_label in METRICS.items():
            value = metric(frame, source_label, report_date)
            if key in {"revenue", "net_profit", "operating_cash_flow"}:
                value = value / 1e8 if value is not None else None
                row[f"{key}_{label}_yi"] = value
            else:
                row[f"{key}_{label}_pct"] = value

    row["ocf_to_net_profit_2025"] = ratio(
        row.get("operating_cash_flow_2025_yi"), row.get("net_profit_2025_yi")
    )
    row["revenue_growth_2025_pct"] = (
        (ratio(row.get("revenue_2025_yi"), row.get("revenue_2024_yi")) - 1) * 100
        if ratio(row.get("revenue_2025_yi"), row.get("revenue_2024_yi")) is not None
        else None
    )
    row["net_profit_growth_2025_pct"] = (
        (ratio(row.get("net_profit_2025_yi"), row.get("net_profit_2024_yi")) - 1) * 100
        if ratio(row.get("net_profit_2025_yi"), row.get("net_profit_2024_yi")) is not None
        else None
    )
    row["revenue_growth_2026Q1_pct"] = (
        (ratio(row.get("revenue_2026Q1_yi"), row.get("revenue_2025Q1_yi")) - 1) * 100
        if ratio(row.get("revenue_2026Q1_yi"), row.get("revenue_2025Q1_yi")) is not None
        else None
    )
    row["net_profit_growth_2026Q1_pct"] = (
        (ratio(row.get("net_profit_2026Q1_yi"), row.get("net_profit_2025Q1_yi")) - 1) * 100
        if ratio(row.get("net_profit_2026Q1_yi"), row.get("net_profit_2025Q1_yi")) is not None
        else None
    )
    row["cninfo_2025_annual"] = find_cninfo_report(
        code, "2025年年度报告", "年报", end_date
    )
    row["cninfo_2026_q1"] = find_cninfo_report(
        code, "2026年第一季度报告", "一季报", end_date
    )

    exchange_code = market_prefix(code) + code
    row["sources"] = {
        "eastmoney_financial": (
            "https://emweb.securities.eastmoney.com/PC_HSF10/"
            f"NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={exchange_code}"
        ),
        "eastmoney_quote": (
            f"https://quote.eastmoney.com/{exchange_code.lower()}.html"
        ),
        "tencent_quote_api": f"https://qt.gtimg.cn/q={tencent_code(code)}",
        "financial_provider_note": "AkShare stock_financial_abstract / Eastmoney F10",
    }
    return row


def flatten(row):
    flat = {key: value for key, value in row.items() if not isinstance(value, dict)}
    for parent in ("cninfo_2025_annual", "cninfo_2026_q1", "sources"):
        for key, value in row.get(parent, {}).items():
            flat[f"{parent}_{key}"] = value
    return flat


def download_annuals(rows, source_dir: Path):
    source_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for row in rows:
        report = row.get("cninfo_2025_annual", {})
        url = report.get("pdf_url")
        target = source_dir / f"{row['code']}_{row['name']}_2025_annual.PDF"
        item = {"code": row["code"], "name": row["name"], "url": url, "path": str(target)}
        if not url:
            item.update({"ok": False, "error": report.get("error", "missing URL")})
            manifest.append(item)
            continue
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=90)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise ValueError("response was not a PDF")
            if not target.exists():
                target.write_bytes(response.content)
            item.update({"ok": True, "bytes": len(response.content)})
        except Exception as exc:
            item.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        manifest.append(item)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--download-annuals", action="store_true")
    args = parser.parse_args()

    try:
        cutoff = datetime.strptime(args.as_of, "%Y%m%d")
    except ValueError as exc:
        raise SystemExit("--as-of must use YYYYMMDD") from exc

    output_dir = Path("data/A股风光海上风电核电")
    source_dir = Path("research/source_docs/A股风光海上风电核电")
    output_dir.mkdir(parents=True, exist_ok=True)

    quotes = fetch_quotes()
    end_date = cutoff.strftime("%Y%m%d")
    rows = [
        build_row(code, name, subsector, business, quotes, end_date)
        for code, name, subsector, business in COMPANIES
    ]

    json_path = output_dir / f"financial_shortlist_{args.as_of}.json"
    csv_path = output_dir / f"financial_shortlist_{args.as_of}.csv"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    flat_rows = [flatten(row) for row in rows]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat_rows[0]))
        writer.writeheader()
        writer.writerows(flat_rows)

    if args.download_annuals:
        manifest = download_annuals(rows, source_dir)
        manifest_path = output_dir / f"cninfo_annual_downloads_{args.as_of}.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(json_path.resolve())
    print(csv_path.resolve())
    for row in rows:
        print(
            row["code"],
            row["name"],
            f"PE={row.get('pe_ttm')}",
            f"ROE={row.get('roe_2025_pct')}",
            f"OCF/NP={row.get('ocf_to_net_profit_2025')}",
            f"debt={row.get('debt_asset_2025_pct')}",
        )


if __name__ == "__main__":
    main()
