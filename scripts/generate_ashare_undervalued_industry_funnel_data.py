#!/usr/bin/env python3
"""Generate A-share undervalued industry funnel data.

The script keeps the workflow local and auditable:
- Eastmoney industry board snapshot for sector-level PE/market cap.
- Local quality-screen pass list as the quality whitelist.
- Eastmoney search + Tencent quote for current candidate valuation.
"""

from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
QUALITY_FILE = ROOT / "筛选公司" / "A股召回池" / "去劣筛选结果-20260517.md"
STAMP = datetime.now().strftime("%Y%m%d")

BOARD_CSV = DATA_DIR / f"ashare_undervalued_industry_boards_{STAMP}.csv"
QUALITY_QUOTES_CSV = DATA_DIR / f"ashare_undervalued_quality_quotes_{STAMP}.csv"
BOARD_HITS_CSV = DATA_DIR / f"ashare_undervalued_board_quality_hits_{STAMP}.csv"
SUMMARY_JSON = DATA_DIR / f"ashare_undervalued_industry_summary_{STAMP}.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
OPENER = build_opener(ProxyHandler({}))


def fetch(url: str, *, encoding: str = "utf-8", retries: int = 6) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Referer": "https://quote.eastmoney.com/",
                    "Accept": "application/json,text/plain,*/*",
                    "Connection": "close",
                },
            )
            with OPENER.open(req, timeout=20) as response:
                return response.read().decode(encoding, errors="replace")
        except Exception as exc:  # noqa: BLE001 - keep script dependency-free.
            last_error = exc
            time.sleep(0.8 + attempt * 0.8)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def fetch_json(url: str, params: dict[str, str | int | float]) -> dict:
    full_url = f"{url}?{urlencode(params, safe=':+,')}"
    text = fetch(full_url)
    return json.loads(text)


def fetch_json_with_fallback(
    urls: tuple[str, ...], params: dict[str, str | int | float]
) -> dict:
    """Fetch the same Eastmoney endpoint from the first responsive host."""
    last_error: Exception | None = None
    for url in urls:
        try:
            full_url = f"{url}?{urlencode(params, safe=':+,')}"
            return json.loads(fetch(full_url, retries=2))
        except Exception as exc:  # noqa: BLE001 - report all host failures together.
            last_error = exc
    raise RuntimeError(f"all fallback hosts failed: {last_error}")


def to_float(value) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_quality_pass_list() -> list[dict[str, str]]:
    text = QUALITY_FILE.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []
    sector = ""
    for line in text.splitlines():
        heading = re.match(r"^###\s+\d+\s+(.+?)（", line)
        if heading:
            sector = heading.group(1).strip()
            continue
        if not line.startswith("|") or "通过" not in line:
            continue
        cells = [cell.strip().strip("*") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"公司", "板块", "序号", "------"}:
            continue
        if "排除" in cells[-1]:
            continue
        rows.append({"name": cells[0], "local_sector": sector, "quality_result": cells[-1]})
    return rows


def search_stock(name: str) -> dict[str, str] | None:
    url = "https://searchadapter.eastmoney.com/api/suggest/get"
    params = {
        "input": name,
        "type": "14",
        "token": "D43BF722C8E33BDC906FB84D85E326E8",
        "count": "10",
    }
    data = fetch_json(url, params)
    results = data.get("QuotationCodeTable", {}).get("Data", []) or []
    astocks = [
        r
        for r in results
        if r.get("Classify") == "AStock"
        and re.match(r"^(00|30|60|68|83|87|43)\d{4}$", str(r.get("Code", "")))
    ]
    exact = [r for r in astocks if r.get("Name") == name]
    candidates = exact or astocks
    if not candidates:
        return None
    item = candidates[0]
    return {
        "name": item.get("Name", name),
        "code": item.get("Code", ""),
        "market": "SH" if str(item.get("Code", "")).startswith(("6", "9", "5")) else "SZ",
    }


def qq_symbol(code: str) -> str:
    if code.startswith(("6", "9", "5")):
        return f"sh{code}"
    if code.startswith(("0", "3", "2", "1")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sh{code}"


def parse_qq_quote(raw: str) -> dict[str, dict[str, str]]:
    quotes: dict[str, dict[str, str]] = {}
    for part in raw.split(";"):
        if "=" not in part or '"' not in part:
            continue
        payload = part.split('"', 1)[1].rsplit('"', 1)[0]
        fields = payload.split("~")
        if len(fields) < 49:
            continue
        code = fields[2]
        quotes[code] = {
            "name": fields[1],
            "code": code,
            "price": fields[3],
            "change_pct": fields[32],
            "turnover_amt_wan": fields[37] if len(fields) > 37 else "",
            "turnover_rate": fields[38] if len(fields) > 38 else "",
            "pe": fields[39] if len(fields) > 39 else "",
            "float_market_cap_yi": fields[44] if len(fields) > 44 else "",
            "market_cap_yi": fields[45] if len(fields) > 45 else "",
            "pb": fields[46] if len(fields) > 46 else "",
            "high_52w": fields[47] if len(fields) > 47 else "",
            "low_52w": fields[48] if len(fields) > 48 else "",
        }
    return quotes


def fetch_quotes(codes: list[str]) -> dict[str, dict[str, str]]:
    quotes: dict[str, dict[str, str]] = {}
    for start in range(0, len(codes), 60):
        symbols = ",".join(qq_symbol(code) for code in codes[start : start + 60])
        raw = fetch(f"https://qt.gtimg.cn/q={symbols}", encoding="gbk")
        quotes.update(parse_qq_quote(raw))
        time.sleep(0.2)
    return quotes


def fetch_industry_boards() -> list[dict[str, object]]:
    urls = (
        "https://push2delay.eastmoney.com/api/qt/clist/get",
        "https://push2.eastmoney.com/api/qt/clist/get",
    )
    rows = []
    for page in range(1, 8):
        params = {
            "pn": page,
            "pz": 100,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f20",
            "fs": "m:90+t:2",
            "fields": "f12,f14,f3,f6,f20,f9,f23",
        }
        data = fetch_json_with_fallback(urls, params)
        page_rows = data.get("data", {}).get("diff", []) or []
        rows.extend(page_rows)
        if len(page_rows) < 100:
            break
        time.sleep(0.15)

    boards = []
    seen = set()
    for row in rows:
        if row.get("f12") in seen:
            continue
        seen.add(row.get("f12"))
        pe = to_float(row.get("f9"))
        market_cap_yi = to_float(row.get("f20"))
        turnover_yi = to_float(row.get("f6"))
        boards.append(
            {
                "board_code": row.get("f12"),
                "board_name": row.get("f14"),
                "change_pct": to_float(row.get("f3")),
                "turnover_yi": round(turnover_yi / 100000000, 2) if turnover_yi else None,
                "market_cap_yi": round(market_cap_yi / 100000000, 2) if market_cap_yi else None,
                "pe": pe,
                "pb": to_float(row.get("f23")),
            }
        )
    return boards


def fetch_board_constituents(board_code: str, limit: int = 80) -> list[dict[str, object]]:
    urls = (
        "https://push2delay.eastmoney.com/api/qt/clist/get",
        "https://push2.eastmoney.com/api/qt/clist/get",
    )
    params = {
        "pn": 1,
        "pz": limit,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f20",
        "fs": f"b:{board_code}",
        "fields": "f12,f14,f2,f3,f6,f20,f9,f23",
    }
    try:
        data = fetch_json_with_fallback(urls, params)
    except RuntimeError as exc:
        print(f"warn: skip board {board_code}: {exc}")
        return []
    rows = data.get("data", {}).get("diff", []) or []
    result = []
    for row in rows:
        market_cap = to_float(row.get("f20"))
        turnover = to_float(row.get("f6"))
        result.append(
            {
                "code": row.get("f12"),
                "name": row.get("f14"),
                "price": to_float(row.get("f2")),
                "change_pct": to_float(row.get("f3")),
                "turnover_yi": round(turnover / 100000000, 2) if turnover else None,
                "market_cap_yi": round(market_cap / 100000000, 2) if market_cap else None,
                "pe": to_float(row.get("f9")),
                "pb": to_float(row.get("f23")),
            }
        )
    return result


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    quality = parse_quality_pass_list()
    for item in quality:
        info = search_stock(item["name"])
        if info:
            item.update(info)
        time.sleep(0.12)

    codes = [item["code"] for item in quality if item.get("code")]
    quotes = fetch_quotes(codes)
    for item in quality:
        quote = quotes.get(item.get("code", ""), {})
        item.update(
            {
                "price": quote.get("price", ""),
                "change_pct": quote.get("change_pct", ""),
                "market_cap_yi": quote.get("market_cap_yi", ""),
                "float_market_cap_yi": quote.get("float_market_cap_yi", ""),
                "pe": quote.get("pe", ""),
                "pb": quote.get("pb", ""),
                "turnover_rate": quote.get("turnover_rate", ""),
                "high_52w": quote.get("high_52w", ""),
                "low_52w": quote.get("low_52w", ""),
            }
        )

    boards = fetch_industry_boards()
    positive_boards = [
        row
        for row in boards
        if row["pe"] is not None
        and row["pe"] > 0
        and row["market_cap_yi"] is not None
        and row["market_cap_yi"] >= 500
    ]
    positive_boards.sort(key=lambda row: (row["pe"], -(row["market_cap_yi"] or 0)))

    quality_names = {item["name"]: item for item in quality}
    board_hits = []
    for board in positive_boards[:120]:
        constituents = fetch_board_constituents(str(board["board_code"]))
        hits = [c for c in constituents if c["name"] in quality_names]
        if not hits:
            continue
        hit_pes = [c["pe"] for c in hits if c["pe"] is not None and c["pe"] > 0]
        hit_pbs = [c["pb"] for c in hits if c["pb"] is not None and c["pb"] > 0]
        board_hits.append(
            {
                "board_code": board["board_code"],
                "board_name": board["board_name"],
                "board_pe": board["pe"],
                "board_market_cap_yi": board["market_cap_yi"],
                "board_change_pct": board["change_pct"],
                "quality_hit_count": len(hits),
                "quality_hit_names": "、".join(c["name"] for c in hits[:12]),
                "quality_hit_median_pe": round(sorted(hit_pes)[len(hit_pes) // 2], 2) if hit_pes else "",
                "quality_hit_median_pb": round(sorted(hit_pbs)[len(hit_pbs) // 2], 2) if hit_pbs else "",
            }
        )
        time.sleep(0.15)

    board_hits.sort(
        key=lambda row: (
            row["board_pe"] if row["board_pe"] is not None else 999,
            -row["quality_hit_count"],
            -(row["board_market_cap_yi"] or 0),
        )
    )

    write_csv(
        BOARD_CSV,
        boards,
        ["board_code", "board_name", "pe", "pb", "market_cap_yi", "turnover_yi", "change_pct"],
    )
    write_csv(
        QUALITY_QUOTES_CSV,
        quality,
        [
            "local_sector",
            "quality_result",
            "name",
            "code",
            "market",
            "price",
            "pe",
            "pb",
            "market_cap_yi",
            "float_market_cap_yi",
            "change_pct",
            "turnover_rate",
            "high_52w",
            "low_52w",
        ],
    )
    write_csv(
        BOARD_HITS_CSV,
        board_hits,
        [
            "board_code",
            "board_name",
            "board_pe",
            "board_market_cap_yi",
            "board_change_pct",
            "quality_hit_count",
            "quality_hit_names",
            "quality_hit_median_pe",
            "quality_hit_median_pb",
        ],
    )

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_urls": {
            "eastmoney_boards": "https://push2.eastmoney.com/api/qt/clist/get?fs=m:90+t:2",
            "eastmoney_boards_fallback": "https://push2delay.eastmoney.com/api/qt/clist/get?fs=m:90+t:2",
            "eastmoney_board_constituents": "https://push2.eastmoney.com/api/qt/clist/get?fs=b:{board_code}",
            "eastmoney_search": "https://searchadapter.eastmoney.com/api/suggest/get",
            "tencent_quote": "https://qt.gtimg.cn/q={symbols}",
            "local_quality_file": str(QUALITY_FILE.relative_to(ROOT)),
        },
        "counts": {
            "quality_companies": len(quality),
            "quality_codes_found": len(codes),
            "boards": len(boards),
            "positive_large_boards": len(positive_boards),
            "board_hits": len(board_hits),
        },
        "outputs": {
            "boards_csv": str(BOARD_CSV.relative_to(ROOT)),
            "quality_quotes_csv": str(QUALITY_QUOTES_CSV.relative_to(ROOT)),
            "board_hits_csv": str(BOARD_HITS_CSV.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
