"""Fetch public ICBC evidence for the 2026-07-13 investment-team report."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests


CODE = "601398"
AS_OF = "2026-07-13"
DATA_DIR = Path("data") / CODE
SOURCE_DIR = Path("research/source_docs") / "工商银行"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SOURCE_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


session = requests.Session()
session.trust_env = False
session.headers.update({"User-Agent": "Mozilla/5.0"})
errors: list[dict[str, str]] = []


def get(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30):
    try:
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response
    except Exception as exc:  # Keep every source failure visible in the evidence bundle.
        errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return None


def parse_tencent(raw: str) -> dict[str, object]:
    payload = raw.split('"', 2)[1]
    fields = payload.split("~")
    is_hk = fields[0] == "100"
    common = {
        "name": fields[1],
        "code": fields[2],
        "price": fields[3],
        "previous_close": fields[4],
        "open": fields[5],
        "timestamp": fields[30],
        "change": fields[31],
        "change_pct": fields[32],
        "high": fields[33],
        "low": fields[34],
        "turnover_amount_10k": fields[37],
        "turnover_rate_pct": fields[38],
        "pe": fields[39],
        "float_market_cap_100m": fields[44],
        "total_market_cap_100m": fields[45],
        "raw_fields": fields,
    }
    if is_hk:
        common.update(
            {
                "pb": fields[65],
                "dividend_yield_pct": fields[47],
                "high_52w": fields[48],
                "low_52w": fields[49],
                "float_shares": fields[70],
                "total_shares": fields[69],
                "currency": fields[75],
            }
        )
    else:
        common.update(
            {
                "pb": fields[46],
                "high_52w": fields[47],
                "low_52w": fields[48],
                "float_shares": fields[72] if len(fields) > 72 else None,
                "total_shares": fields[73] if len(fields) > 73 else None,
                "currency": fields[82] if len(fields) > 82 else None,
            }
        )
    return common


quotes: dict[str, object] = {"as_of": AS_OF, "sources": {}}
for symbol in ("sh601398", "hk01398"):
    url = f"http://qt.gtimg.cn/q={symbol}"
    response = get(url)
    if response is not None:
        raw = response.content.decode("gbk", errors="replace")
        quotes["sources"][f"tencent_{symbol}"] = {
            "url": url,
            "parsed": parse_tencent(raw),
            "raw": raw,
        }


sina_url = "http://hq.sinajs.cn/list=sh601398,hk01398"
sina_response = get(sina_url, headers={"Referer": "https://finance.sina.com.cn/"})
if sina_response is not None:
    quotes["sources"]["sina"] = {
        "url": sina_url,
        "raw": sina_response.content.decode("gbk", errors="replace"),
    }


eastmoney_quote_url = (
    "http://push2.eastmoney.com/api/qt/stock/get?"
    "secid=1.601398&fields=f57,f58,f43,f44,f45,f46,f47,f48,f60,f84,"
    "f116,f117,f162,f167,f170,f171"
)
eastmoney_quote_response = get(
    eastmoney_quote_url,
    headers={"Referer": "https://quote.eastmoney.com/"},
)
if eastmoney_quote_response is not None:
    quotes["sources"]["eastmoney"] = {
        "url": eastmoney_quote_url,
        "raw": eastmoney_quote_response.json(),
    }
write_json(DATA_DIR / "market_snapshot_20260713.json", quotes)


eastmoney_finance_url = (
    "http://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/"
    "ZYZBAjaxNew?type=1&code=SH601398"
)
eastmoney_finance_response = get(
    eastmoney_finance_url,
    headers={"Referer": "https://emweb.securities.eastmoney.com/"},
)
if eastmoney_finance_response is not None:
    write_json(
        DATA_DIR / "eastmoney_finance_snapshot_20260713.json",
        eastmoney_finance_response.json(),
    )


def fetch_sse(keyword: str) -> dict[str, object] | None:
    params = {
        "isPagination": "true",
        "productId": CODE,
        "keyWord": keyword,
        "securityType": "0101,120100,020100,020200,120200",
        "reportType2": "",
        "reportType": "ALL",
        "beginDate": "2025-01-01",
        "endDate": AS_OF,
        "pageHelp.pageSize": "100",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
    }
    url = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?" + urlencode(params)
    response = get(
        url,
        headers={
            "Referer": "https://www.sse.com.cn/assortment/stock/list/info/announcement/",
            "Accept": "application/json,*/*",
        },
    )
    return response.json() if response is not None else None


sse_results: dict[str, object] = {}
for keyword in ("2025年年度报告", "2026年第一季度报告", "利润分配", "资本补充"):
    result = fetch_sse(keyword)
    if result is not None:
        sse_results[keyword] = result
write_json(DATA_DIR / "sse_announcements_20260713.json", sse_results)


def fetch_cninfo(category: str) -> dict[str, object] | None:
    url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
    payload = {
        "pageNum": "1",
        "pageSize": "30",
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "601398,jjxt0000019",
        "searchkey": "",
        "secid": "",
        "category": category,
        "trade": "",
        "seDate": "2025-01-01~2026-07-13",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    try:
        response = session.post(
            url,
            data=payload,
            headers={
                "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch",
                "Accept": "application/json,*/*",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return None


cninfo_results: dict[str, object] = {}
for label, category in (
    ("annual", "category_ndbg_szsh"),
    ("q1", "category_yjdbg_szsh"),
):
    result = fetch_cninfo(category)
    if result is not None:
        cninfo_results[label] = result
write_json(DATA_DIR / "cninfo_announcements_20260713.json", cninfo_results)


selected: dict[str, dict[str, object]] = {}
for keyword, result in sse_results.items():
    rows = result.get("pageHelp", {}).get("data", [])
    for row in rows:
        title = str(row.get("TITLE", ""))
        if "年度报告摘要" in title:
            continue
        if (
            (keyword == "2025年年度报告" and "2025年年度报告" in title)
            or (keyword == "2026年第一季度报告" and "2026年第一季度报告" in title)
            or (keyword in {"利润分配", "资本补充"} and keyword in title)
        ):
            url = "https://www.sse.com.cn" + str(row.get("URL", ""))
            selected[url] = row


try:
    import pypdf
except ImportError:
    pypdf = None

download_manifest: list[dict[str, object]] = []
for url, row in selected.items():
    response = get(url, headers={"Referer": "https://www.sse.com.cn/"}, timeout=60)
    title = str(row.get("TITLE", "report")).replace("/", "-")
    entry: dict[str, object] = {
        "title": title,
        "date": row.get("SSEDATE"),
        "url": url,
        "status": "failed",
    }
    if response is not None and response.content.startswith(b"%PDF"):
        pdf_path = SOURCE_DIR / f"{title}.pdf"
        pdf_path.write_bytes(response.content)
        entry.update({"status": "downloaded", "path": str(pdf_path), "bytes": len(response.content)})
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(str(pdf_path))
                pages = [
                    f"\n--- page {number} ---\n{page.extract_text() or ''}"
                    for number, page in enumerate(reader.pages, start=1)
                ]
                text_path = pdf_path.with_suffix(".txt")
                text_path.write_text("\n".join(pages), encoding="utf-8")
                entry.update({"text_path": str(text_path), "pages": len(reader.pages)})
            except Exception as exc:
                entry["extract_error"] = f"{type(exc).__name__}: {exc}"
    download_manifest.append(entry)


cninfo_selected: dict[str, dict[str, object]] = {}
for label, result in cninfo_results.items():
    for row in result.get("announcements", []):
        title = str(row.get("announcementTitle", "")).replace("<em>", "").replace("</em>", "")
        is_target = (
            label == "annual"
            and "2025年度报告" in title
            and "摘要" not in title
            and "英文" not in title
        ) or (
            label == "q1"
            and "2026年第一季度报告" in title
            and "英文" not in title
        )
        adjunct_url = str(row.get("adjunctUrl", ""))
        if is_target and adjunct_url:
            cninfo_selected["https://static.cninfo.com.cn/" + adjunct_url.lstrip("/")] = row


for url, row in cninfo_selected.items():
    response = get(url, headers={"Referer": "http://www.cninfo.com.cn/"}, timeout=60)
    title = (
        str(row.get("announcementTitle", "report"))
        .replace("<em>", "")
        .replace("</em>", "")
        .replace("/", "-")
    )
    entry = {
        "title": title,
        "date": row.get("announcementTime"),
        "url": url,
        "announcement_id": row.get("announcementId"),
        "status": "failed",
    }
    if response is not None and response.content.startswith(b"%PDF"):
        pdf_path = SOURCE_DIR / f"{title}-cninfo.pdf"
        pdf_path.write_bytes(response.content)
        entry.update({"status": "downloaded", "path": str(pdf_path), "bytes": len(response.content)})
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(str(pdf_path))
                pages = [
                    f"\n--- page {number} ---\n{page.extract_text() or ''}"
                    for number, page in enumerate(reader.pages, start=1)
                ]
                text_path = pdf_path.with_suffix(".txt")
                text_path.write_text("\n".join(pages), encoding="utf-8")
                entry.update({"text_path": str(text_path), "pages": len(reader.pages)})
            except Exception as exc:
                entry["extract_error"] = f"{type(exc).__name__}: {exc}"
    download_manifest.append(entry)
write_json(SOURCE_DIR / "download_manifest_20260713.json", download_manifest)


# AkShare is an independent wrapper source. Remove stale proxy variables before import/use.
for key in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(key, None)

try:
    import akshare as ak

    calls = {
        "financial_abstract": lambda: ak.stock_financial_abstract(symbol=CODE),
        "indicator_sina": lambda: ak.stock_financial_analysis_indicator(symbol=CODE),
        "indicator_eastmoney": lambda: ak.stock_financial_analysis_indicator_em(symbol=CODE),
        "disclosure_annual_cninfo": lambda: ak.stock_zh_a_disclosure_report_cninfo(
            symbol=CODE,
            market="沪深京",
            category="年报",
            start_date="20250101",
            end_date="20260713",
        ),
        "disclosure_q1_cninfo": lambda: ak.stock_zh_a_disclosure_report_cninfo(
            symbol=CODE,
            market="沪深京",
            category="一季报",
            start_date="20250101",
            end_date="20260713",
        ),
        "history_eastmoney": lambda: ak.stock_zh_a_hist(
            symbol=CODE,
            period="daily",
            start_date="20260713",
            end_date="20260713",
            adjust="",
        ),
    }
    for name, call in calls.items():
        try:
            frame = call()
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f"Expected DataFrame, got {type(frame).__name__}")
            frame.to_csv(
                DATA_DIR / f"akshare_{name}_20260713.csv",
                index=False,
                encoding="utf-8-sig",
            )
        except Exception as exc:
            errors.append({"source": f"akshare:{name}", "error": f"{type(exc).__name__}: {exc}"})
except Exception as exc:
    errors.append({"source": "akshare:import", "error": f"{type(exc).__name__}: {exc}"})


write_json(DATA_DIR / "fetch_errors_20260713.json", errors)
print(json.dumps({"quotes": list(quotes["sources"]), "downloads": download_manifest, "errors": errors}, ensure_ascii=False, indent=2))
