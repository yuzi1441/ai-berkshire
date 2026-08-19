#!/usr/bin/env python3
"""Refresh A-share annual-report disclosure dates for the decision dashboard.

The snapshot keeps two different facts separate:

* the latest completed annual report's actual disclosure date;
* the next annual report's effective scheduled date, when an exchange or data
  provider has published one.

Eastmoney provides a compact full-market appointment table. CNINFO's bulk
appointment table is used as an independent cross-check for the latest actual
date and for future appointments. Missing future appointments remain null and
are displayed by the dashboard as ``未公布``; no date is inferred from a
statutory reporting window.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
EASTMONEY_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
CNINFO_URL = "https://www.cninfo.com.cn/new/information/getPrbookInfo"
EASTMONEY_PAGE_SIZE = 500
CNINFO_PAGE_SIZE = 10000
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
USER_AGENT = "ai-berkshire-annual-report-dates/1.0"
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")


class AnnualDateError(RuntimeError):
    """Raised when a required source cannot be read or parsed."""


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from error


def normalized_date(value: Any) -> str | None:
    if value is None:
        return None
    match = DATE_RE.search(str(value))
    return match.group(1) if match else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def fetch_json(url: str, params: dict[str, Any], *, method: str = "GET") -> Any:
    encoded = urlencode(params).encode("utf-8")
    if method == "POST":
        request = Request(
            url,
            data=encoded,
            headers={
                "User-Agent": USER_AGENT,
                "Origin": "https://www.cninfo.com.cn",
                "Referer": "https://www.cninfo.com.cn/",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            method="POST",
        )
    else:
        request = Request(
            f"{url}?{encoded.decode('utf-8')}",
            headers={"User-Agent": USER_AGENT, "Referer": "https://data.eastmoney.com/"},
        )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed provider URLs
            return json.loads(response.read())
    except Exception as error:  # noqa: BLE001 - provider errors are reported together
        raise AnnualDateError(f"failed to fetch {url}: {error}") from error


def board_universe(board_path: Path) -> list[dict[str, str]]:
    try:
        payload = json.loads(board_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnnualDateError(f"invalid decision board: {board_path}: {error}") from error
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise AnnualDateError(f"decision board has no decisions list: {board_path}")
    universe = []
    for item in decisions:
        if not isinstance(item, dict) or item.get("market") != "A股":
            continue
        ticker = str(item.get("ticker") or "").upper()
        company = str(item.get("company") or "").strip()
        if ticker and company:
            universe.append({"ticker": ticker, "company": company})
    return sorted(universe, key=lambda item: (item["company"], item["ticker"]))


def code_from_ticker(ticker: str) -> str:
    return ticker.split(".", 1)[0]


def eastmoney_filter(report_period: str) -> str:
    return (
        '(SECURITY_TYPE_CODE in ("058001001","058001008"))'
        f"(REPORT_DATE='{report_period}')"
    )


def fetch_eastmoney_period(report_period: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    page = 1
    while True:
        payload = fetch_json(
            EASTMONEY_URL,
            {
                "sortColumns": "FIRST_APPOINT_DATE,SECURITY_CODE",
                "sortTypes": "1,1",
                "pageSize": EASTMONEY_PAGE_SIZE,
                "pageNumber": page,
                "reportName": "RPT_PUBLIC_BS_APPOIN",
                "columns": "ALL",
                "filter": eastmoney_filter(report_period),
            },
        )
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict) or not result.get("data"):
            # The provider returns success=false and no result before the next
            # annual appointment table is published. That is a valid "未公布".
            if page == 1 and isinstance(payload, dict) and payload.get("message") == "返回数据为空":
                return {}
            if page == 1:
                raise AnnualDateError(f"Eastmoney returned no annual data for {report_period}")
            break
        for row in result.get("data") or []:
            if isinstance(row, dict) and row.get("SECURITY_CODE"):
                rows[str(row["SECURITY_CODE"]).zfill(6)] = row
        pages = int(result.get("pages") or page)
        if page >= pages:
            break
        page += 1
    return rows


def fetch_cninfo_market(market: str, report_period: str) -> dict[str, dict[str, Any]]:
    payload = fetch_json(
        CNINFO_URL,
        {
            "sectionTime": report_period,
            "firstTime": "",
            "lastTime": "",
            "market": market,
            "stockCode": "",
            "orderClos": "",
            "isDesc": "true",
            "pagesize": CNINFO_PAGE_SIZE,
            "pagenum": "1",
        },
        method="POST",
    )
    rows = payload.get("prbookinfos") if isinstance(payload, dict) else None
    if rows is None and isinstance(payload, dict) and int(payload.get("totalRows") or 0) == 0:
        # The next annual appointment table is commonly absent until the
        # exchanges publish it. This is a valid empty schedule, not a source
        # failure.
        return {}
    if not isinstance(rows, list):
        raise AnnualDateError(f"CNINFO returned no appointment list for {market} {report_period}")
    return {
        str(row.get("seccode")).zfill(6): row
        for row in rows
        if isinstance(row, dict) and row.get("seccode")
    }


def effective_appointment(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    for key in ("THIRD_CHANGE_DATE", "SECOND_CHANGE_DATE", "FIRST_CHANGE_DATE", "FIRST_APPOINT_DATE"):
        if value := normalized_date(row.get(key)):
            return value
    return None


def cninfo_effective_appointment(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    for key in ("f005d_0102", "f004d_0102", "f003d_0102", "f002d_0102"):
        if value := normalized_date(row.get(key)):
            return value
    return None


def cninfo_actual(row: dict[str, Any] | None) -> str | None:
    # CNINFO field f006d_0102 is the actual disclosure date; f002d_0102 is
    # the first appointment date. They are often equal, but not always.
    return normalized_date(row.get("f006d_0102")) if row else None


def build_snapshot(repo_root: Path, as_of: date) -> dict[str, Any]:
    universe = board_universe(repo_root / "data" / "investment-dashboard" / "decision_board.json")
    latest_period = date(as_of.year - 1, 12, 31).isoformat()
    next_period = date(as_of.year, 12, 31).isoformat()
    eastmoney_latest = fetch_eastmoney_period(latest_period)
    eastmoney_next = fetch_eastmoney_period(next_period)
    cninfo_latest = fetch_cninfo_market("szsh", latest_period)
    cninfo_latest.update(fetch_cninfo_market("bj", latest_period))
    cninfo_next = fetch_cninfo_market("szsh", next_period)
    cninfo_next.update(fetch_cninfo_market("bj", next_period))

    records: list[dict[str, Any]] = []
    for item in universe:
        ticker = item["ticker"]
        code = code_from_ticker(ticker)
        em_latest = eastmoney_latest.get(code)
        em_next = eastmoney_next.get(code)
        ci_latest = cninfo_latest.get(code)
        ci_next = cninfo_next.get(code)
        eastmoney_actual = normalized_date((em_latest or {}).get("ACTUAL_PUBLISH_DATE"))
        cninfo_actual_date = cninfo_actual(ci_latest)
        next_eastmoney = effective_appointment(em_next)
        next_cninfo = cninfo_effective_appointment(ci_next)
        next_actual = normalized_date((em_next or {}).get("ACTUAL_PUBLISH_DATE")) or cninfo_actual(ci_next)
        if eastmoney_actual and cninfo_actual_date:
            verification = "cross_checked" if eastmoney_actual == cninfo_actual_date else "source_mismatch"
        elif eastmoney_actual or cninfo_actual_date:
            verification = "single_source"
        else:
            verification = "missing"
        scheduled = next_eastmoney or next_cninfo
        records.append(
            {
                "company": item["company"],
                "ticker": ticker,
                "market": "A股",
                "latest_report_period": latest_period,
                "latest_actual_disclosure_date": eastmoney_actual or cninfo_actual_date,
                "latest_actual_eastmoney": eastmoney_actual,
                "latest_actual_cninfo": cninfo_actual_date,
                "latest_actual_verification": verification,
                "next_report_period": next_period,
                "next_scheduled_disclosure_date": scheduled if not next_actual else None,
                "next_scheduled_eastmoney": next_eastmoney,
                "next_scheduled_cninfo": next_cninfo,
                "next_actual_disclosure_date": next_actual,
                "next_status": "已披露" if next_actual else "已预约" if scheduled else "未公布",
                "sources": {
                    "eastmoney": "https://datacenter.eastmoney.com/securities/api/data/v1/get",
                    "cninfo": "https://www.cninfo.com.cn/new/commonUrl?url=data/yuyuepilu",
                },
            }
        )
    missing_latest = sum(not item.get("latest_actual_disclosure_date") for item in records)
    next_scheduled_count = sum(bool(item.get("next_scheduled_disclosure_date")) for item in records)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(SHANGHAI_TIMEZONE).isoformat(timespec="seconds"),
        "data_cutoff": as_of.isoformat(),
        "market": "A股",
        "universe": "current decision board A-share stocks",
        "latest_report_period": latest_period,
        "next_report_period": next_period,
        "record_count": len(records),
        "missing_latest_actual_count": missing_latest,
        "next_scheduled_count": next_scheduled_count,
        "source_policy": "Eastmoney primary appointment table + CNINFO independent cross-check; no estimated dates",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--as-of", type=parse_date, default=datetime.now(SHANGHAI_TIMEZONE).date())
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "investment-dashboard" / "annual_report_dates.json",
    )
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    output = arguments.output if arguments.output.is_absolute() else repo_root / arguments.output
    try:
        payload = build_snapshot(repo_root, arguments.as_of)
        write_json(output.resolve(), payload)
        site_output = repo_root / "site" / "data" / "annual_report_dates.json"
        write_json(site_output, payload)
    except (AnnualDateError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(
        f"Updated {payload['record_count']} A-share annual-date records; "
        f"latest missing {payload['missing_latest_actual_count']}, "
        f"next scheduled {payload['next_scheduled_count']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
