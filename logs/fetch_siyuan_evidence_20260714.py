from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "research" / "source_docs" / "思源电气"
DATA_DIR = ROOT / "data" / "002028"

CNINFO_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": (
        "https://www.cninfo.com.cn/new/disclosure/stock?"
        "stockCode=002028&orgId=gssz0002028"
    ),
}

DOCUMENTS = {
    "思源电气-2026年半年度业绩快报-20260711.pdf": (
        "https://static.cninfo.com.cn/finalpage/2026-07-11/1225420017.PDF"
    ),
    "思源电气-思源东芝股权变更登记-20260710.pdf": (
        "https://static.cninfo.com.cn/finalpage/2026-07-10/1225416830.PDF"
    ),
    "思源电气-投资者关系活动记录表-20260709.pdf": (
        "http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/"
        "CNSESZ_STOCK/2026/2026-7/2026-07-09/12437614.PDF"
    ),
    "思源电气-H股申请版本-20260211.pdf": (
        "https://www1.hkexnews.hk/app/sehk/2026/108195/documents/"
        "sehk26021100490.pdf"
    ),
}

EASTMONEY_PERFORMANCE_URL = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get?"
    "reportName=RPT_FCI_PERFORMANCEE&columns=ALL&"
    "filter=(SECURITY_CODE%3D%22002028%22)&pageNumber=1&pageSize=50&"
    "sortColumns=REPORT_DATE&sortTypes=-1"
)


def download(session: requests.Session, url: str, destination: Path) -> None:
    response = session.get(url, headers=CNINFO_HEADERS, timeout=60)
    response.raise_for_status()
    destination.write_bytes(response.content)


def extract_pdf_text(pdf_path: Path) -> Path:
    text_path = pdf_path.with_suffix(".txt")
    pages = []
    for page in PdfReader(pdf_path).pages:
        pages.append(page.extract_text() or "")
    text_path.write_text("\n\n".join(pages), encoding="utf-8")
    return text_path


def fetch_cninfo_index(session: requests.Session) -> list[dict[str, object]]:
    payload = {
        "pageNum": 1,
        "pageSize": 50,
        "column": "szse",
        "tabName": "fulltext",
        "plate": "sz",
        "stock": "002028,gssz0002028",
        "searchkey": "",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": "2026-07-01~2026-07-14",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = session.post(
        CNINFO_URL,
        data=payload,
        headers=CNINFO_HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    announcements = response.json().get("announcements") or []
    return [
        {
            "title": item.get("announcementTitle"),
            "announcement_time": item.get("announcementTime"),
            "announcement_id": item.get("announcementId"),
            "url": "https://static.cninfo.com.cn/" + item.get("adjunctUrl", ""),
        }
        for item in announcements
    ]


def fetch_quote(session: requests.Session) -> dict[str, object]:
    tencent_response = session.get(
        "https://qt.gtimg.cn/q=sz002028",
        headers={"Referer": "https://gu.qq.com", "User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    tencent_response.raise_for_status()
    tencent_text = tencent_response.content.decode("gb18030", errors="replace")
    (DATA_DIR / "tencent-quote-20260714.txt").write_text(
        tencent_text, encoding="utf-8"
    )

    sina_response = session.get(
        "https://hq.sinajs.cn/list=sz002028",
        headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=30,
    )
    sina_response.raise_for_status()
    sina_text = sina_response.content.decode("gb18030", errors="replace")
    (DATA_DIR / "sina-quote-20260714.txt").write_text(sina_text, encoding="utf-8")

    tencent_fields = tencent_text.split('"')[1].split("~")
    sina_fields = sina_text.split('"')[1].split(",")
    return {
        "fetched_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "tencent": {
            "price": float(tencent_fields[3]),
            "previous_close": float(tencent_fields[4]),
            "timestamp": tencent_fields[30],
            "market_cap_100m_cny": float(tencent_fields[45]),
            "float_shares": int(tencent_fields[72]),
            "total_shares": int(tencent_fields[73]),
        },
        "sina": {
            "price": float(sina_fields[3]),
            "previous_close": float(sina_fields[2]),
            "date": sina_fields[30],
            "time": sina_fields[31],
        },
    }


def fetch_eastmoney_performance(session: requests.Session) -> dict[str, object]:
    response = session.get(
        EASTMONEY_PERFORMANCE_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://data.eastmoney.com/",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    (DATA_DIR / "eastmoney-performance-express-20260714.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    records = payload.get("result", {}).get("data", [])
    latest = next(record for record in records if record.get("QDATE") == "2026Q2")
    return {
        "source_url": EASTMONEY_PERFORMANCE_URL,
        "report_date": latest.get("REPORT_DATE"),
        "notice_date": latest.get("NOTICE_DATE"),
        "revenue_cny": latest.get("TOTAL_OPERATE_INCOME"),
        "parent_net_profit_cny": latest.get("PARENT_NETPROFIT"),
        "basic_eps_cny": latest.get("BASIC_EPS"),
        "bvps_cny": latest.get("PARENT_BVPS"),
        "weighted_roe_percent": latest.get("WEIGHTAVG_ROE"),
        "revenue_yoy_percent": latest.get("YSTZ"),
        "parent_net_profit_yoy_percent": latest.get("JLRTBZCL"),
    }


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.trust_env = False

    for filename, url in DOCUMENTS.items():
        pdf_path = SOURCE_DIR / filename
        download(session, url, pdf_path)
        extract_pdf_text(pdf_path)

    announcement_index = fetch_cninfo_index(session)
    quote = fetch_quote(session)
    eastmoney_performance = fetch_eastmoney_performance(session)
    snapshot = {
        "cutoff_date": "2026-07-14",
        "company": "思源电气",
        "ticker": "002028.SZ",
        "announcements": announcement_index,
        "quote": quote,
        "eastmoney_performance": eastmoney_performance,
    }
    (DATA_DIR / "investment-team-snapshot-20260714.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
