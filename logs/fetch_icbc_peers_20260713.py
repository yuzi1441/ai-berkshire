"""Fetch same-cutoff public data for ICBC and major Chinese bank peers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import requests


DATA_DIR = Path("data/601398")
PEERS = {
    "601398": "工商银行",
    "601939": "建设银行",
    "601288": "农业银行",
    "601988": "中国银行",
    "600036": "招商银行",
}
session = requests.Session()
session.trust_env = False
session.headers.update({"User-Agent": "Mozilla/5.0"})
errors = []


def get(url, headers=None):
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response
    except Exception as exc:
        errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        return None


def parse_tencent(raw):
    fields = raw.split('"', 2)[1].split("~")
    return {
        "name": fields[1],
        "code": fields[2],
        "price_cny": fields[3],
        "timestamp": fields[30],
        "change_pct": fields[32],
        "pe_tencent": fields[39],
        "market_cap_100m_cny": fields[45],
        "pb_tencent": fields[46],
        "high_52w": fields[47],
        "low_52w": fields[48],
        "total_shares": fields[73] if len(fields) > 73 else None,
    }


quote_evidence = {"as_of": "2026-07-13", "tencent": {}, "sina_raw": ""}
symbols = ",".join(f"sh{code}" for code in PEERS)
tencent_response = get(f"http://qt.gtimg.cn/q={symbols}")
if tencent_response is not None:
    text = tencent_response.content.decode("gbk", errors="replace")
    for raw_line in text.splitlines():
        if '="' in raw_line:
            parsed = parse_tencent(raw_line)
            quote_evidence["tencent"][parsed["code"]] = {"parsed": parsed, "raw": raw_line}

sina_response = get(
    f"http://hq.sinajs.cn/list={symbols}",
    headers={"Referer": "https://finance.sina.com.cn/"},
)
if sina_response is not None:
    quote_evidence["sina_raw"] = sina_response.content.decode("gbk", errors="replace")
(DATA_DIR / "peer_quotes_20260713.json").write_text(
    json.dumps(quote_evidence, ensure_ascii=False, indent=2), encoding="utf-8"
)


raw_financials = {}
rows = []
for code, expected_name in PEERS.items():
    url = (
        "http://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/"
        f"ZYZBAjaxNew?type=1&code=SH{code}"
    )
    response = get(url, headers={"Referer": "https://emweb.securities.eastmoney.com/"})
    if response is None:
        continue
    payload = response.json()
    raw_financials[code] = payload
    annual = next(
        (
            item
            for item in payload.get("data", [])
            if item.get("REPORT_TYPE") == "年报" and item.get("REPORT_YEAR") == "2025"
        ),
        None,
    )
    if annual is None:
        errors.append({"source": code, "error": "No 2025 annual record"})
        continue
    quote = quote_evidence["tencent"].get(code, {}).get("parsed", {})
    rows.append(
        {
            "code": code,
            "name": annual.get("SECURITY_NAME_ABBR", expected_name),
            "price_cny_20260713": quote.get("price_cny"),
            "portal_pe": quote.get("pe_tencent"),
            "portal_pb": quote.get("pb_tencent"),
            "portal_a_price_equivalent_market_cap_100m_cny": quote.get("market_cap_100m_cny"),
            "static_2025a_pe": round(float(quote.get("price_cny")) / float(annual.get("EPSJB")), 4),
            "static_2025a_pb": round(float(quote.get("price_cny")) / float(annual.get("BPS")), 4),
            "revenue_100m_cny": round(annual.get("TOTALOPERATEREVE", 0) / 100_000_000, 2),
            "parent_net_profit_100m_cny": round(annual.get("PARENTNETPROFIT", 0) / 100_000_000, 2),
            "eps_cny": annual.get("EPSJB"),
            "bvps_cny": annual.get("BPS"),
            "roe_pct": annual.get("ROEJQ"),
            "roa_pct": annual.get("ZZCJLL"),
            "net_interest_margin_pct": annual.get("NET_INTEREST_MARGIN"),
            "net_interest_spread_pct": annual.get("NET_INTEREST_SPREAD"),
            "npl_ratio_pct": annual.get("NONPERLOAN"),
            "provision_coverage_pct": annual.get("BLDKBBL"),
            "cet1_ratio_pct": annual.get("HXYJBCZL"),
            "capital_adequacy_pct": annual.get("NEWCAPITALADER"),
            "cost_income_ratio_pct": annual.get("REVENUE_RATIO"),
            "gross_loans_100m_cny": round(annual.get("GROSSLOANS", 0) / 100_000_000, 2),
        }
    )


(DATA_DIR / "peer_eastmoney_finance_raw_20260713.json").write_text(
    json.dumps(raw_financials, ensure_ascii=False, indent=2), encoding="utf-8"
)
with (DATA_DIR / "peer_comparison_2025.csv").open("w", newline="", encoding="utf-8-sig") as handle:
    if rows:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
(DATA_DIR / "peer_fetch_errors_20260713.json").write_text(
    json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({"peer_rows": rows, "errors": errors}, ensure_ascii=False, indent=2))
