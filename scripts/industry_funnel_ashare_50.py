"""Build a 50-stock A-share funnel from the inclusive quality pool.

The input quality screen covers all current Shanghai, Shenzhen and Beijing
A-shares, including financial and explicitly cyclical industries. This script
adds a dated valuation snapshot, verifies prices with Tencent quotes, applies a
balance-sheet gate to ordinary companies, uses a financial-specific score for
financial companies, and keeps a decision/reason for every quality-passed row.
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
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "A股市场" / "quality-screen-ashare-all-20260804.json"
DEFAULT_AS_OF = datetime.now().astimezone().strftime("%Y-%m-%d")
DEFAULT_JSON = ROOT / "data" / "A股市场" / f"industry-funnel-ashare-50-{DEFAULT_AS_OF.replace('-', '')}.json"
DEFAULT_CSV = ROOT / "data" / "A股市场" / f"industry-funnel-ashare-50-{DEFAULT_AS_OF.replace('-', '')}.csv"
DEFAULT_REPORT = ROOT / "reports" / "A股全市场行业漏斗50家" / f"ashare-quality-funnel-50-{DEFAULT_AS_OF.replace('-', '')}.md"

EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
TENCENT_URL = "https://qt.gtimg.cn/q="
F10_URL = "https://datacenter.eastmoney.com/securities/api/data/get"
EASTMONEY_FIELDS = "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f37,f38,f39,f40,f41,f45,f46,f49,f57,f58,f60,f100"
PAGE_SIZE_F10 = 5000
SECONDARY_CYCLICAL_RE = re.compile(
    r"煤炭|石油|油气|采掘|钢铁|有色金属|贵金属|小金属|能源金属|"
    r"化学原料|化学制品|化肥|农化|农药|橡胶|塑料|水泥|玻璃|玻纤|建材|"
    r"建筑材料|建筑装饰|基础建设|基建|专业工程|房地产|航运|港口|航空机场|"
    r"铁路公路|汽车整车|汽车零部件|汽车服务|工程机械|燃气"
)

# A bounded first-pass moat review for the final queue. This is deliberately
# conservative and is not a substitute for the company-level annual-report
# review that follows the funnel.
MOAT_QUICK = {
    "601156": (4, "航空货运网络、机场资源与客户认证形成规模/网络壁垒"),
    "000858": (5, "高端白酒品牌、渠道和消费心智"),
    "600167": (4, "区域供热管网、特许经营和长期客户关系"),
    "600398": (3, "大众服饰品牌、渠道与供应链规模"),
    "000651": (4, "家电品牌、制造规模、渠道和服务网络"),
    "002027": (4, "核心楼宇媒体点位网络和规模化销售系统"),
    "300861": (4, "金刚石线技术、客户认证和制造规模"),
    "000568": (4, "白酒品牌、产品结构和经销商网络"),
    "603233": (4, "连锁药房规模、选址网络和经营资质"),
    "002035": (3, "厨卫品牌、渠道覆盖和产品迭代"),
    "603587": (3, "中高端女装品牌、设计与渠道"),
    "000513": (4, "药品注册、产品组合和医药商业化能力"),
    "000848": (3, "植物蛋白饮料品牌和渠道"),
    "601900": (3, "出版发行资质、内容版权和区域渠道"),
    "002818": (3, "家居卖场区位、商户网络和运营能力"),
    "002508": (4, "厨电品牌、渠道与服务体系"),
    "600163": (3, "发电资产、项目资源与电力运营经验"),
    "920003": (3, "工程咨询资质、专业经验和客户关系；小市值需复核"),
    "601877": (4, "低压电器品牌、渠道和制造规模"),
    "600380": (3, "药品注册、成熟产品和医药商业化能力"),
    "002034": (3, "固废处理项目资质、特许经营和运营经验"),
    "002555": (3, "游戏研发发行、IP运营和流量投放能力；竞争激烈"),
    "600887": (4, "乳品品牌、冷链渠道和规模采购"),
    "600809": (4, "白酒品牌、产品升级和经销商网络"),
    "600566": (3, "核心产品品牌、注册壁垒和渠道"),
    "300770": (3, "IPTV平台运营资质、内容分发和区域用户基础"),
    "603387": (3, "体外诊断产品注册、渠道和客户验证"),
    "300888": (4, "医疗耗材品牌、质量体系和渠道"),
    "601019": (3, "出版发行资质、内容版权和渠道"),
    "601827": (3, "垃圾焚烧项目特许经营、运营和规模"),
}


def as_decimal(value: object) -> Decimal | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def as_float(value: object) -> float | None:
    number = as_decimal(value)
    return float(number) if number is not None else None


def request_text(url: str, *, encoding: str = "utf-8", timeout: int = 30, retries: int = 4) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 ai-berkshire-industry-funnel/1.0", "Accept": "*/*"},
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode(encoding, errors="replace")
        except Exception as error:  # keep network retries bounded and visible
            last_error = error
            if attempt + 1 < retries:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}: {last_error}") from last_error


def market_id(exchange: str) -> str:
    return "1" if exchange == "SH" else "0"


def normalized_exchange(code: str, exchange: str) -> str:
    """Repair the prior screen's exchange fallback for 4/8/92 BSE codes."""
    if code.startswith(("4", "8", "92")):
        return "BJ"
    if code.startswith("6"):
        return "SH"
    return exchange if exchange in {"SH", "SZ"} else "SZ"


def tencent_symbol(row: dict) -> str:
    exchange = str(row.get("exchange") or "SZ").lower()
    return f"{exchange}{str(row['code']).zfill(6)}"


def fetch_eastmoney(rows: list[dict]) -> tuple[dict[str, dict], str | None]:
    quotes: dict[str, dict] = {}
    for start in range(0, len(rows), 250):
        batch = rows[start : start + 250]
        secids = ",".join(f"{market_id(row['exchange'])}.{row['code']}" for row in batch)
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": EASTMONEY_FIELDS,
            "secids": secids,
        }
        url = f"{EASTMONEY_URL}?{urllib.parse.urlencode(params)}"
        payload = json.loads(request_text(url))
        for item in ((payload.get("data") or {}).get("diff") or []):
            code = str(item.get("f12") or "").zfill(6)
            if code:
                quotes[code] = {
                    "price": as_float(item.get("f2")),
                    "change_pct": as_float(item.get("f3")),
                    "turnover_pct": as_float(item.get("f8")),
                    "pe_ttm": as_float(item.get("f9")),
                    "pb": as_float(item.get("f23")),
                    "market_cap": as_float(item.get("f20")),
                    "free_float_market_cap": as_float(item.get("f21")),
                    "name": str(item.get("f14") or ""),
                    "industry_quote": str(item.get("f100") or ""),
                }
        print(f"Eastmoney quote batch {min(start + 250, len(rows))}/{len(rows)}", flush=True)
    return quotes, None


def fetch_tencent(rows: list[dict]) -> tuple[dict[str, dict], str | None]:
    quotes: dict[str, dict] = {}
    latest_timestamp: str | None = None
    for start in range(0, len(rows), 50):
        batch = rows[start : start + 50]
        symbols = [tencent_symbol(row) for row in batch]
        payload = request_text(f"{TENCENT_URL}{','.join(symbols)}", encoding="gb18030")
        for row, symbol in zip(batch, symbols):
            match = re.search(rf'v_{re.escape(symbol)}="([^"]*)"', payload)
            if not match:
                continue
            fields = match.group(1).split("~")
            if len(fields) < 6:
                continue
            try:
                price = float(fields[3])
                previous_close = float(fields[4])
            except (ValueError, IndexError):
                continue
            if price <= 0:
                continue
            timestamp_index = next(
                (index for index, field in enumerate(fields) if re.fullmatch(r"20\d{12}", field or "")),
                None,
            )
            change_pct = None
            if timestamp_index is not None and timestamp_index + 2 < len(fields):
                change_pct = as_float(fields[timestamp_index + 2])
                latest_timestamp = max(latest_timestamp or "", fields[timestamp_index])
            if change_pct is None and previous_close > 0:
                change_pct = (price - previous_close) / previous_close * 100
            quotes[row["code"]] = {
                "price": price,
                "previous_close": previous_close,
                "change_pct": change_pct,
                "provider_timestamp": fields[timestamp_index] if timestamp_index is not None else None,
            }
        print(f"Tencent quote batch {min(start + 50, len(rows))}/{len(rows)}", flush=True)
    return quotes, latest_timestamp


def fetch_annual_debt_ratio() -> dict[str, float | None]:
    """Fetch 2025 year-end asset-liability ratios for the candidate universe."""
    params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA",
        "sty": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_YEAR,ZCFZL",
        "filter": "(REPORT_YEAR=2025)",
        "p": "1",
        "ps": str(PAGE_SIZE_F10),
        "sr": "1",
        "st": "SECURITY_CODE",
        "source": "HSF10",
        "client": "PC",
    }
    first = json.loads(request_text(f"{F10_URL}?{urllib.parse.urlencode(params)}", timeout=120))
    result = first.get("result") or {}
    pages = int(result.get("pages") or 0)
    rows = list(result.get("data") or [])
    for page in range(2, pages + 1):
        page_params = dict(params)
        page_params["p"] = str(page)
        response = json.loads(request_text(f"{F10_URL}?{urllib.parse.urlencode(page_params)}", timeout=120))
        rows.extend((response.get("result") or {}).get("data") or [])
        print(f"annual debt page {page}/{pages}", flush=True)
    ratios: dict[str, float | None] = {}
    for row in rows:
        code = str(row.get("SECURITY_CODE") or "").zfill(6)
        if code:
            ratios[code] = as_float(row.get("ZCFZL"))
    return ratios


def threshold_score(value: float | None, thresholds: list[tuple[float, int]], missing: int = 0) -> int:
    if value is None:
        return missing
    for lower_bound, points in thresholds:
        if value >= lower_bound:
            return points
    return 0


def score_row(row: dict) -> dict:
    values = row.get("values") or {}
    quote = row.get("quote") or {}
    financial_special = row.get("original_scope") == "金融" or str(row.get("result") or "").startswith("金融特殊")
    roe = as_float(values.get("roe_avg_10"))
    ocfni = as_float(values.get("ocf_ni_avg_5"))
    fcf = as_float(values.get("fcf_5_total"))
    market_cap = as_float(quote.get("market_cap"))
    fcf_to_market_cap = fcf / market_cap if fcf is not None and market_cap and market_cap > 0 else None
    gross_margin = as_float(values.get("gross_margin_avg_5"))
    net_margin = as_float(values.get("net_margin_avg_10"))
    share_inflation = as_float(values.get("share_inflation_5"))
    pe = as_float(quote.get("pe_ttm"))
    pb = as_float(quote.get("pb"))
    roe_points = threshold_score(roe, [(25, 15), (20, 13), (15, 11), (10, 8), (8, 6)])
    share_points = threshold_score(None if share_inflation is None else 0.20 - share_inflation, [(0.20, 6), (0.10, 5), (0, 3)])
    if financial_special:
        # Bank/insurer/broker margins and industrial cash-flow ratios are not
        # comparable. Keep the score on a 60-point scale using ROE and share
        # stability only, while retaining the quality-screen special result.
        quality = round(roe_points / 15 * 40 + share_points / 6 * 20, 2)
        quality_basis = "金融特殊口径：ROE 40分、股本稳定性20分"
    else:
        quality = (
            roe_points
            + threshold_score(ocfni, [(1.5, 12), (1.2, 10), (1.0, 8), (0.8, 6), (0.7, 4)])
            + threshold_score(fcf_to_market_cap, [(0.30, 12), (0.15, 10), (0.08, 8), (0.03, 6), (0, 3)])
            + threshold_score(gross_margin, [(50, 8), (30, 7), (20, 6), (15, 4)])
            + threshold_score(net_margin, [(20, 7), (10, 6), (5, 4)])
            + share_points
        )
        quality_basis = "普通行业：ROE、现金流、FCF、市值稳定性、毛利率和净利率"
    valuation = (
        threshold_score(None if pe is None or pe <= 0 else 100 - pe, [(88, 18), (82, 15), (75, 12), (65, 8), (50, 4)])
        + threshold_score(None if pb is None or pb <= 0 else 15 - pb, [(13.5, 12), (12, 10), (10, 7), (7, 4)])
    )
    current_valuation_usable = bool(pe is not None and 0 < pe <= 80 and pb is not None and 0 < pb <= 12)
    debt_ratio = as_float(row.get("debt_ratio"))
    industry = row.get("industry") or ""
    debt_limit = None if financial_special else 70 if re.search(r"电力|燃气|水务|环保|公用事业|机场|港口|铁路", industry) else 60
    if financial_special:
        debt_gate = "金融特殊口径"
    elif debt_ratio is None:
        debt_gate = "数据不足"
    elif debt_ratio <= debt_limit:
        debt_gate = "通过"
    else:
        debt_gate = "不通过"
    quote_cross = row.get("quote_cross_check") or {}
    if financial_special:
        secondary_scope = "金融行业（特殊口径）"
    elif row.get("original_scope") == "周期":
        secondary_scope = "周期行业（本次保留）"
    else:
        secondary_scope = "普通行业"
    row.update(
        {
            "derived": {
                "fcf_to_market_cap_5y": round(fcf_to_market_cap, 8) if fcf_to_market_cap is not None else None,
                "quality_score": quality,
                "quality_score_basis": quality_basis,
                "valuation_score": valuation,
                "composite_score": quality + valuation,
                "current_valuation_usable": current_valuation_usable,
                "price_cross_check": quote_cross.get("status", "unavailable"),
                "debt_limit": debt_limit,
                "debt_gate": debt_gate,
            },
            "eligibility": "可比估值" if current_valuation_usable else "估值不可比",
            "secondary_scope": secondary_scope,
        }
    )
    if current_valuation_usable and debt_gate == "不通过":
        row["eligibility"] = "资产负债率超标"
    elif current_valuation_usable and debt_gate == "数据不足":
        row["eligibility"] = "负债率数据不足"
    moat_score, moat_basis = MOAT_QUICK.get(row.get("code"), (None, "未完成护城河初评"))
    row["moat_quick"] = {
        "score": moat_score,
        "rating": f"{moat_score}/5" if moat_score is not None else "待评",
        "basis": moat_basis,
        "status": "初评达到★★★" if moat_score is not None and moat_score >= 3 else "待核验",
    }
    row["hard_gates"] = {
        "pe_pb": "通过" if current_valuation_usable else "不通过",
        "roe": "通过" if roe is not None and roe >= 15 else "质量池保留/趋势复核",
        "operating_cashflow": "金融特殊口径" if financial_special else "通过" if ocfni is not None and ocfni >= 0.7 else "待复核",
        "debt_ratio": debt_gate,
        "moat": row["moat_quick"]["status"],
    }
    return row


def select_rows(rows: list[dict], selection_count: int, industry_cap: int) -> tuple[list[dict], list[dict]]:
    eligible = [
        row for row in rows
        if row["derived"]["current_valuation_usable"] and row["derived"].get("debt_gate") in {"通过", "金融特殊口径"}
    ]
    ordered = sorted(
        eligible,
        key=lambda row: (
            -row["derived"]["composite_score"],
            -row["derived"]["quality_score"],
            -(as_float((row.get("quote") or {}).get("market_cap")) or 0),
            row["code"],
        ),
    )
    for rank, row in enumerate(ordered, 1):
        row["derived"]["global_rank"] = rank

    selected: list[dict] = []
    industry_counts: Counter[str] = Counter()
    for row in ordered:
        industry = row.get("industry") or "未分类"
        if industry_counts[industry] >= industry_cap:
            continue
        selected.append(row)
        industry_counts[industry] += 1
        if len(selected) == selection_count:
            break
    if len(selected) < selection_count:
        selected_codes = {row["code"] for row in selected}
        for row in ordered:
            if row["code"] not in selected_codes:
                selected.append(row)
                selected_codes.add(row["code"])
                if len(selected) == selection_count:
                    break
    selected_codes = {row["code"] for row in selected}
    selected_industries = Counter(row.get("industry") or "未分类" for row in selected)
    for rank, row in enumerate(selected, 1):
        row["selection_rank"] = rank
        row["decision"] = f"入选{selection_count}家"
        row["decision_reason"] = "综合得分靠前，且满足 PE/PB 可比、普通行业负债率门槛与行业分散上限"
    for row in rows:
        if row["code"] in selected_codes:
            continue
        if row["eligibility"] == "资产负债率超标":
            row["decision"] = "淘汰"
            row["decision_reason"] = "2025年报资产负债率超过普通行业门槛（公用事业放宽至70%）"
        elif row["eligibility"] == "负债率数据不足":
            row["decision"] = "淘汰"
            row["decision_reason"] = "缺少2025年报资产负债率，未满足本层硬门槛"
        elif row["eligibility"] != "可比估值":
            row["decision"] = "淘汰"
            row["decision_reason"] = "当前 PE/PB 缺失、为负或超出本轮可比估值上限"
        elif selected_industries[row.get("industry") or "未分类"] >= industry_cap:
            row["decision"] = "淘汰"
            row["decision_reason"] = f"行业分散上限：同一细分行业最多入选{industry_cap}家"
        else:
            row["decision"] = "淘汰"
            row["decision_reason"] = f"综合得分未进入前{selection_count}"
    return selected, ordered


def fmt(value: object, digits: int = 2) -> str:
    number = as_float(value)
    return "数据不足" if number is None else f"{number:.{digits}f}"


def fmt_pct(value: object, digits: int = 1) -> str:
    number = as_float(value)
    return "数据不足" if number is None else f"{number * 100:.{digits}f}%"


def fmt_yi(value: object) -> str:
    number = as_float(value)
    return "数据不足" if number is None else f"{number / 100_000_000:.1f}"


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "selection_rank", "global_rank", "code", "name", "exchange", "industry", "original_scope", "result", "secondary_scope", "decision",
        "decision_reason", "price", "pe_ttm", "pb", "market_cap_yi", "change_pct", "turnover_pct",
        "roe_avg_10", "gross_margin_avg_5", "ocf_ni_avg_5", "net_margin_avg_10", "fcf_5_total_yi",
        "fcf_to_market_cap_5y", "share_inflation_5", "debt_ratio", "debt_limit", "debt_gate",
        "quality_score", "quality_score_basis", "valuation_score", "composite_score",
        "price_cross_check", "quote_timestamp", "moat_rating", "moat_basis", "moat_status",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            values = row.get("values") or {}
            quote = row.get("quote") or {}
            derived = row.get("derived") or {}
            cross = row.get("quote_cross_check") or {}
            writer.writerow(
                {
                    "selection_rank": row.get("selection_rank"),
                    "global_rank": derived.get("global_rank"),
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "exchange": row.get("exchange"),
                    "industry": row.get("industry"),
                    "original_scope": row.get("original_scope"),
                    "result": row.get("result"),
                    "secondary_scope": row.get("secondary_scope"),
                    "decision": row.get("decision"),
                    "decision_reason": row.get("decision_reason"),
                    "price": quote.get("price"),
                    "pe_ttm": quote.get("pe_ttm"),
                    "pb": quote.get("pb"),
                    "market_cap_yi": (as_float(quote.get("market_cap")) or 0) / 100_000_000 if quote.get("market_cap") is not None else None,
                    "change_pct": quote.get("change_pct"),
                    "turnover_pct": quote.get("turnover_pct"),
                    "roe_avg_10": values.get("roe_avg_10"),
                    "gross_margin_avg_5": values.get("gross_margin_avg_5"),
                    "ocf_ni_avg_5": values.get("ocf_ni_avg_5"),
                    "net_margin_avg_10": values.get("net_margin_avg_10"),
                    "fcf_5_total_yi": (as_float(values.get("fcf_5_total")) or 0) / 100_000_000 if values.get("fcf_5_total") is not None else None,
                    "fcf_to_market_cap_5y": derived.get("fcf_to_market_cap_5y"),
                    "share_inflation_5": values.get("share_inflation_5"),
                    "debt_ratio": row.get("debt_ratio"),
                    "debt_limit": derived.get("debt_limit"),
                    "debt_gate": derived.get("debt_gate"),
                    "quality_score": derived.get("quality_score"),
                    "quality_score_basis": derived.get("quality_score_basis"),
                    "valuation_score": derived.get("valuation_score"),
                    "composite_score": derived.get("composite_score"),
                    "price_cross_check": cross.get("status", "unavailable"),
                    "quote_timestamp": cross.get("provider_timestamp"),
                    "moat_rating": (row.get("moat_quick") or {}).get("rating"),
                    "moat_basis": (row.get("moat_quick") or {}).get("basis"),
                    "moat_status": (row.get("moat_quick") or {}).get("status"),
                }
            )


def build_report(payload: dict, path: Path) -> None:
    target = int(payload["rules"]["selection_count"])
    selection_label = f"入选{target}家"
    selected = sorted(
        [row for row in payload["records"] if row.get("decision") == selection_label],
        key=lambda row: row.get("selection_rank") or 999,
    )
    records = payload["records"]
    quote_available = sum(bool(row.get("quote")) for row in records)
    valuation_usable = sum(row.get("eligibility") == "可比估值" for row in records)
    debt_passed = sum((row.get("derived") or {}).get("debt_gate") in {"通过", "金融特殊口径"} for row in records)
    debt_blocked = sum((row.get("derived") or {}).get("debt_gate") in {"不通过", "数据不足"} for row in records)
    cross_ok = sum((row.get("quote_cross_check") or {}).get("status") == "一致" for row in records)
    industry_counts = Counter(row.get("industry") or "未分类" for row in selected)
    scope_counts = Counter(row.get("original_scope") or "保留" for row in selected)
    financial_count = sum(row.get("original_scope") == "金融" for row in records)
    cyclical_count = sum(row.get("original_scope") == "周期" for row in records)
    quote_time = payload.get("quote_timestamp") or "未返回"
    lines: list[str] = [
        "# A股全市场行业漏斗：50家候选（包含金融与周期）",
        "",
        f"> 研究日期：{payload['as_of']}  ",
        f"> 财务数据截止：{payload['financial_cutoff']}  ",
        f"> 行情快照：{payload['as_of']}，腾讯行情时间 {quote_time}  ",
        "> 市场范围：沪深京 A 股；本轮包含金融和周期行业，起点为全市场质量通过/豁免池。  ",
        "> 研究性质：50只优先研究候选，不等同于买入清单或投资建议。",
        "",
        "## 结论",
        "",
        f"从全市场 {payload['input_counts']['all_market_previous']} 家中，质量筛选通过/豁免 {payload['input_counts']['quality_pool']} 家；其中本层候选含金融 {financial_count} 家、周期 {cyclical_count} 家。取得东方财富行情 {quote_available} 家，负债率数据通过或金融特殊口径 {debt_passed} 家，同时满足 PE/PB 与负债率门槛 {valuation_usable} 家，最终按综合分和细分行业最多 {payload['rules']['industry_cap']} 家选出 {len(selected)} 家。价格交叉核对一致 {cross_ok}/{len(records)} 家。",
        "",
        f"这 {len(selected)} 家是下一轮逐家公司研究的优先队列，不是同时买入的组合。金融公司的工业毛利率、OCF/净利和FCF收益率不参与同口径评分；护城河仍有待逐家公司年报核验，因此不输出买入价和仓位。",
        "",
        "## 漏斗记录",
        "",
        "| 层级 | 家数 | 规则 |",
        "|---|---:|---|",
        f"| 全市场质量母池 | {payload['input_counts']['all_market_previous']} | 沪深京 A 股，金融和周期均包含 |",
        f"| 质量通过/豁免池 | {payload['input_counts']['quality_pool']} | 七项质量指标通过/豁免；其余记录留在质量筛选报告 |",
        f"| 行情可得 | {quote_available} | 东方财富返回价格、PE、PB、市值 |",
        f"| 估值可比 | {valuation_usable} | 0 < PE ≤ 80 且 0 < PB ≤ 12 |",
        f"| 负债率数据通过 | {debt_passed} | 普通行业≤60%；电力/公用事业等放宽至70%；金融特殊口径；统计全候选池 |",
        f"| 负债率阻断 | {debt_blocked} | 超标或数据不足，不进入本层候选 |",
        f"| PE/PB+负债率可比 | {valuation_usable} | 同时满足估值和资产负债率门槛 |",
        f"| 最终入选 | {len(selected)} | 综合分排序 + 行业最多{payload['rules']['industry_cap']}家 |",
        "",
        "## 评分口径",
        "",
        "普通行业质量分 60 分：平均 ROE 15、5年 OCF/净利润 12、5年累计 FCF/当前市值 12、平均毛利率 8、平均净利率 7、股本稳定性 6。金融特殊质量分改为 ROE 40 分 + 股本稳定性 20 分，不把工业毛利率、OCF/净利和 FCF/市值强行横比。估值分 30 分：PE 18、PB 12。",
        "",
        "硬门槛是为了排除当前不可比的亏损、极高估值、极高 PB 和普通行业高负债公司，并不代表 PE 80、PB 12 或负债率60%是合理买点。行业上限是分散约束，不是行业质量判断。",
        "",
        f"## 入选{target}家",
        "",
        "| 排名 | 公司 | 代码 | 行业 | 原始分类 | 价格 | 市值(亿元) | PE | PB | ROE均值 | OCF/净利 | 负债率 | 5年FCF/市值 | 综合分 | 护城河初评 |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for row in selected:
        values = row.get("values") or {}
        quote = row.get("quote") or {}
        derived = row.get("derived") or {}
        moat = row.get("moat_quick") or {}
        pe = as_float(quote.get("pe_ttm"))
        financial_special = row.get("original_scope") == "金融"
        ocfni_display = "金融特殊口径" if financial_special else fmt(values.get("ocf_ni_avg_5"))
        fcf_display = "金融特殊口径" if financial_special else fmt_pct(derived.get("fcf_to_market_cap_5y"))
        debt_display = "金融特殊口径" if financial_special else f"{fmt(row.get('debt_ratio'))}%" if row.get("debt_ratio") is not None else "数据不足"
        lines.append(
            f"| {row.get('selection_rank')} | {row.get('name')} | {row.get('code')}.{row.get('exchange')} | {row.get('industry') or '未分类'} | {row.get('original_scope') or '保留'} | {fmt(quote.get('price'))} | {fmt_yi(quote.get('market_cap'))} | {fmt(quote.get('pe_ttm'))} | {fmt(quote.get('pb'))} | {fmt(values.get('roe_avg_10'))}% | {ocfni_display} | {debt_display} | {fcf_display} | {derived.get('composite_score')} | {moat.get('rating', '待评')} |"
        )
    lines.extend(
        [
            "",
            "### 行业分布",
            "",
            "; ".join(f"{industry} {count}家" for industry, count in sorted(industry_counts.items(), key=lambda item: (-item[1], item[0]))),
            "",
            "### 原始行业分类分布",
            "",
            "; ".join(f"{scope} {count}家" for scope, count in sorted(scope_counts.items(), key=lambda item: (-item[1], item[0]))),
            "",
            "## 淘汰记录",
            "",
            f"质量通过/豁免池内 {len(records)} 家的代码、当前估值、负债率、综合分和逐家公司淘汰理由已保存在配套 CSV/JSON；上一层质量筛选未通过或数据不足的 {payload['input_counts']['all_market_previous'] - payload['input_counts']['quality_pool']} 家，保留在全市场质量筛选报告中。",
            "",
            "| 淘汰原因 | 家数 |",
            "|---|---:|",
        ]
    )
    reasons = Counter(row.get("decision_reason") for row in records if row.get("decision") != selection_label)
    for reason, count in reasons.most_common():
        lines.append(f"| {reason} | {count} |")
    lines.extend(
        [
            "",
            "## 风险与下一步",
            "",
            "1. PE/PB 是东方财富快照字段，随盘中价格和财报更新变化；没有历史分位，不能单凭绝对倍数判断便宜。",
            "2. 负债率取2025年报批量字段；公用事业放宽门槛是筛选假设，不是对资本结构风险的豁免。",
            "3. 金融公司只在金融可比口径下排序；银行、保险、证券的负债率、毛利率、OCF/净利和FCF收益率不能与工业公司横比。",
            f"4. 护城河初评只覆盖既有人工映射，其他候选标记为待核验；这 {len(selected)} 家仍需逐家核对品牌、牌照、转换成本、规模或技术壁垒。",
            f"5. 下一步应对{len(selected)}家做巨潮年报 + 东方财富逐项复核，再按公司质量、价格安全边际、Bull/Bear证据分别形成公司报告。",
            "",
            "## 来源与审计状态",
            "",
            f"- 上一轮质量池：`{payload['input_path']}`；财务截止 {payload['financial_cutoff']}。",
            f"- 东方财富行情：`{EASTMONEY_URL}`，字段包括价格、PE、PB、总市值、行业。",
            f"- 腾讯行情交叉源：`{TENCENT_URL}`，用于价格和行情时间核对。",
            f"- 2025年报资产负债率：`{F10_URL}`（RPT_F10_FINANCE_MAINFINADATA / ZCFZL）。",
            f"- 审计状态：报告数据抽检固定种子42提取30个点；逐点巨潮副源值尚未填入，不能把本报告视为最终双源审计 PASS。",
            "",
            "## AI研究偏见自觉",
            "",
            "本轮从已有质量池出发，天然偏向有完整财务数据且通过旧门槛的公司；行业上限会降低单一行业集中，但也可能排除同一行业中排名第4的优质公司。量化评分无法替代商业模式、管理层和竞争结构研究。",
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
    parser.add_argument("--selection-count", type=int, default=50)
    parser.add_argument("--industry-cap", type=int, default=3)
    parser.add_argument("--reuse-existing", action="store_true", help="reuse the existing same-day quote snapshot")
    args = parser.parse_args()

    input_payload = json.loads(args.input.read_text(encoding="utf-8"))
    pass_results = {"通过", "豁免A通过", "豁免B通过", "金融特殊口径通过"}
    candidates = []
    for source_row in input_payload["records"]:
        if source_row.get("scope") != "全市场" or source_row.get("result") not in pass_results:
            continue
        row = json.loads(json.dumps(source_row, ensure_ascii=False))
        row["exchange"] = normalized_exchange(row["code"], str(row.get("exchange") or ""))
        candidates.append(row)
    debt_ratios = fetch_annual_debt_ratio()
    for row in candidates:
        row["debt_ratio"] = debt_ratios.get(row["code"])
    existing_payload = None
    if args.reuse_existing and args.json.exists():
        existing_payload = json.loads(args.json.read_text(encoding="utf-8"))
    if existing_payload and len(existing_payload.get("records", [])) == len(candidates):
        existing_by_code = {row.get("code"): row for row in existing_payload["records"]}
        for row in candidates:
            prior = existing_by_code.get(row["code"]) or {}
            row["quote"] = prior.get("quote") or {}
            row["quote_cross_check"] = prior.get("quote_cross_check") or {}
        eastmoney = {row["code"]: row.get("quote") or {} for row in candidates}
        tencent = {}
        quote_timestamp = existing_payload.get("quote_timestamp")
    else:
        existing_payload = None
        eastmoney, _ = fetch_eastmoney(candidates)
        tencent, quote_timestamp = fetch_tencent(candidates)
    records: list[dict] = []
    for source_row in candidates:
        row = json.loads(json.dumps(source_row, ensure_ascii=False))
        code = row["code"]
        if not existing_payload:
            row["quote"] = eastmoney.get(code, {})
        em_price = as_float((row.get("quote") or {}).get("price"))
        tq = tencent.get(code, {})
        if existing_payload:
            prior_cross = row.get("quote_cross_check") or {}
            tq = {"price": prior_cross.get("tencent_price"), "provider_timestamp": prior_cross.get("provider_timestamp")}
        tq_price = as_float(tq.get("price"))
        diff_pct = abs(em_price - tq_price) / tq_price * 100 if em_price is not None and tq_price else None
        row["quote_cross_check"] = {
            "status": "一致" if diff_pct is not None and diff_pct <= 1 else "有差异" if diff_pct is not None else "不可得",
            "eastmoney_price": em_price,
            "tencent_price": tq_price,
            "difference_pct": round(diff_pct, 6) if diff_pct is not None else None,
            "provider_timestamp": tq.get("provider_timestamp"),
        }
        records.append(score_row(row))
    selected, ordered = select_rows(records, args.selection_count, args.industry_cap)
    del selected, ordered
    payload = {
        "schema_version": 1,
        "as_of": args.as_of,
        "financial_cutoff": input_payload.get("financial_cutoff", "2025-12-31"),
        "quote_timestamp": quote_timestamp,
        "scope": "沪深京A股；包含金融与周期行业的全市场质量池行业漏斗",
        "input_path": str(args.input),
        "input_counts": {"quality_pool": len(candidates), "all_market_previous": len(input_payload.get("records", []))},
        "rules": {
            "valuation_gate": "0 < PE <= 80 and 0 < PB <= 12",
            "debt_gate": "普通行业资产负债率<=60%；电力/燃气/水务/环保/公用事业/机场/港口/铁路<=70%；金融特殊口径",
            "industry_cap": args.industry_cap,
            "quality_score_max": 60,
            "valuation_score_max": 30,
            "selection_count": args.selection_count,
        },
        "sources": {
            "quality_pool": input_payload.get("sources"),
            "eastmoney_quotes": EASTMONEY_URL,
            "tencent_quotes": TENCENT_URL,
            "annual_debt_ratio": F10_URL,
        },
        "counts": dict(Counter(row.get("decision") for row in records)),
        "records": records,
        "json_path": str(args.json),
        "csv_path": str(args.csv),
        "report_path": str(args.report),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(records, args.csv)
    build_report(payload, args.report)
    print(json.dumps({"json": str(args.json), "csv": str(args.csv), "report": str(args.report), "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
