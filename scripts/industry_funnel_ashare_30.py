"""Build a second-pass 30-stock funnel from the A-share quality pool.

The input quality screen has already removed financial and explicitly cyclical
industries. This script adds a dated valuation snapshot, verifies prices with
Tencent quotes, ranks the remaining companies, and keeps a decision/reason
for every input row.
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
DEFAULT_INPUT = ROOT / "data" / "A股市场" / "quality-screen-ashare-excluding-financial-cyclical-20260804.json"
DEFAULT_AS_OF = datetime.now().astimezone().strftime("%Y-%m-%d")
DEFAULT_JSON = ROOT / "data" / "A股市场" / f"industry-funnel-ashare-30-{DEFAULT_AS_OF.replace('-', '')}.json"
DEFAULT_CSV = ROOT / "data" / "A股市场" / f"industry-funnel-ashare-30-{DEFAULT_AS_OF.replace('-', '')}.csv"
DEFAULT_REPORT = ROOT / "reports" / "A股去金融周期二次漏斗30家" / f"ashare-quality-funnel-30-{DEFAULT_AS_OF.replace('-', '')}.md"

EASTMONEY_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
TENCENT_URL = "https://qt.gtimg.cn/q="
EASTMONEY_FIELDS = "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f37,f38,f39,f40,f41,f45,f46,f49,f57,f58,f60,f100"
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

    quality = (
        threshold_score(roe, [(25, 15), (20, 13), (15, 11), (10, 8), (8, 6)])
        + threshold_score(ocfni, [(1.5, 12), (1.2, 10), (1.0, 8), (0.8, 6), (0.7, 4)])
        + threshold_score(fcf_to_market_cap, [(0.30, 12), (0.15, 10), (0.08, 8), (0.03, 6), (0, 3)])
        + threshold_score(gross_margin, [(50, 8), (30, 7), (20, 6), (15, 4)])
        + threshold_score(net_margin, [(20, 7), (10, 6), (5, 4)])
        + threshold_score(None if share_inflation is None else 0.20 - share_inflation, [(0.20, 6), (0.10, 5), (0, 3)])
    )
    valuation = (
        threshold_score(None if pe is None or pe <= 0 else 100 - pe, [(88, 18), (82, 15), (75, 12), (65, 8), (50, 4)])
        + threshold_score(None if pb is None or pb <= 0 else 15 - pb, [(13.5, 12), (12, 10), (10, 7), (7, 4)])
    )
    current_valuation_usable = bool(pe is not None and 0 < pe <= 80 and pb is not None and 0 < pb <= 12)
    quote_cross = row.get("quote_cross_check") or {}
    row.update(
        {
            "derived": {
                "fcf_to_market_cap_5y": round(fcf_to_market_cap, 8) if fcf_to_market_cap is not None else None,
                "quality_score": quality,
                "valuation_score": valuation,
                "composite_score": quality + valuation,
                "current_valuation_usable": current_valuation_usable,
                "price_cross_check": quote_cross.get("status", "unavailable"),
            },
            "eligibility": "可比估值" if current_valuation_usable else "估值不可比",
            "secondary_scope": "周期边界复核排除" if SECONDARY_CYCLICAL_RE.search(row.get("industry") or "") else "保留",
        }
    )
    if row["secondary_scope"] != "保留":
        row["eligibility"] = "周期边界复核排除"
    moat_score, moat_basis = MOAT_QUICK.get(row.get("code"), (None, "未进入30家初评队列"))
    row["moat_quick"] = {
        "score": moat_score,
        "rating": f"{moat_score}/5" if moat_score is not None else "待评",
        "basis": moat_basis,
        "status": "初评达到★★★" if moat_score is not None and moat_score >= 3 else "待核验",
    }
    return row


def select_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    eligible = [
        row for row in rows
        if row["derived"]["current_valuation_usable"] and row.get("secondary_scope") == "保留"
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
        if industry_counts[industry] >= 3:
            continue
        selected.append(row)
        industry_counts[industry] += 1
        if len(selected) == 30:
            break
    if len(selected) < 30:
        selected_codes = {row["code"] for row in selected}
        for row in ordered:
            if row["code"] not in selected_codes:
                selected.append(row)
                selected_codes.add(row["code"])
                if len(selected) == 30:
                    break
    selected_codes = {row["code"] for row in selected}
    selected_industries = Counter(row.get("industry") or "未分类" for row in selected)
    for rank, row in enumerate(selected, 1):
        row["selection_rank"] = rank
        row["decision"] = "入选30家"
        row["decision_reason"] = "综合得分靠前，且满足估值可比门槛与行业分散上限"
    for row in rows:
        if row["code"] in selected_codes:
            continue
        if row["eligibility"] == "周期边界复核排除":
            row["decision"] = "淘汰"
            row["decision_reason"] = "周期边界复核：行业名称命中油气、燃气、建材、农化等周期关键词"
        elif row["eligibility"] != "可比估值":
            row["decision"] = "淘汰"
            row["decision_reason"] = "当前 PE/PB 缺失、为负或超出本轮可比估值上限"
        elif selected_industries[row.get("industry") or "未分类"] >= 3:
            row["decision"] = "淘汰"
            row["decision_reason"] = "行业分散上限：同一细分行业最多入选3家"
        else:
            row["decision"] = "淘汰"
            row["decision_reason"] = "综合得分未进入前30"
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
        "selection_rank", "global_rank", "code", "name", "exchange", "industry", "result", "secondary_scope", "decision",
        "decision_reason", "price", "pe_ttm", "pb", "market_cap_yi", "change_pct", "turnover_pct",
        "roe_avg_10", "gross_margin_avg_5", "ocf_ni_avg_5", "net_margin_avg_10", "fcf_5_total_yi",
        "fcf_to_market_cap_5y", "share_inflation_5", "quality_score", "valuation_score", "composite_score",
        "price_cross_check", "quote_timestamp", "moat_rating", "moat_basis",
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
                    "quality_score": derived.get("quality_score"),
                    "valuation_score": derived.get("valuation_score"),
                    "composite_score": derived.get("composite_score"),
                    "price_cross_check": cross.get("status", "unavailable"),
                    "quote_timestamp": cross.get("provider_timestamp"),
                    "moat_rating": (row.get("moat_quick") or {}).get("rating"),
                    "moat_basis": (row.get("moat_quick") or {}).get("basis"),
                }
            )


def build_report(payload: dict, path: Path) -> None:
    selected = sorted(
        [row for row in payload["records"] if row.get("decision") == "入选30家"],
        key=lambda row: row.get("selection_rank") or 999,
    )
    records = payload["records"]
    quote_available = sum(bool(row.get("quote")) for row in records)
    valuation_usable = sum(row.get("eligibility") == "可比估值" for row in records)
    scope_guard_excluded = sum(row.get("eligibility") == "周期边界复核排除" for row in records)
    cross_ok = sum((row.get("quote_cross_check") or {}).get("status") == "一致" for row in records)
    industry_counts = Counter(row.get("industry") or "未分类" for row in selected)
    quote_time = payload.get("quote_timestamp") or "未返回"
    lines: list[str] = [
        "# A股去金融与周期后的二次漏斗：30家候选",
        "",
        f"> 研究日期：{payload['as_of']}  ",
        f"> 财务数据截止：{payload['financial_cutoff']}  ",
        f"> 行情快照：2026-08-04，腾讯行情时间 {quote_time}  ",
        "> 市场范围：沪深京 A 股；起点是上一轮已剔除金融与周期行业的质量通过/豁免池。  ",
        "> 研究性质：二次候选筛选，不等同于买入清单或投资建议。",
        "",
        "## 结论",
        "",
        f"从上一轮质量池 {payload['input_counts']['quality_pool']} 家中，取得东方财富行情 {quote_available} 家；先做周期边界复核排除 {scope_guard_excluded} 家，再有 {valuation_usable} 家满足本轮 PE/PB 可比门槛，最终按质量与估值综合分并执行单一细分行业最多 3 家，选出 {len(selected)} 家。价格交叉核对一致 {cross_ok}/{len(records)} 家。",
        "",
        "这 30 家是下一轮逐家公司研究的优先队列，不是 30 家同时买入。当前报告没有完成 30 家逐项东方财富 + 巨潮年报双源审计，也没有历史估值分位、管理层和护城河逐家公司深度核验；因此不输出买入价和仓位。",
        "",
        "## 漏斗记录",
        "",
        "| 层级 | 家数 | 规则 |",
        "|---|---:|---|",
        f"| 上一轮去金融/周期质量池 | {payload['input_counts']['quality_pool']} | 2025年报七项质量指标通过或规则豁免 |",
        f"| 行情可得 | {quote_available} | 东方财富返回价格、PE、PB、市值 |",
        f"| 周期边界复核后 | {payload['input_counts']['quality_pool'] - scope_guard_excluded} | 二次复核油气、燃气、建材、农化等明显周期关键词 |",
        f"| 估值可比 | {valuation_usable} | 0 < PE ≤ 80 且 0 < PB ≤ 12 |",
        f"| 最终入选 | {len(selected)} | 综合分排序 + 行业最多3家 |",
        "",
        "## 评分口径",
        "",
        "质量分 60 分：平均 ROE 15、5年 OCF/净利润 12、5年累计 FCF/当前市值 12、平均毛利率 8、平均净利率 7、股本稳定性 6。估值分 30 分：PE 18、PB 12。综合分越高优先级越高；同分按质量分、市值、代码排序。",
        "",
        "硬门槛是为了排除当前不可比的亏损/极高估值/极高 PB 公司，并不代表 PE 80 或 PB 12 是合理买点。行业上限是组合分散约束，不是行业质量判断。",
        "",
        "## 入选30家",
        "",
        "| 排名 | 公司 | 代码 | 行业 | 价格 | 市值(亿元) | PE | PB | ROE均值 | OCF/净利 | 5年FCF/市值 | 综合分 | 护城河初评 | 当前标签 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in selected:
        values = row.get("values") or {}
        quote = row.get("quote") or {}
        derived = row.get("derived") or {}
        moat = row.get("moat_quick") or {}
        pe = as_float(quote.get("pe_ttm"))
        label = "质量+估值" if pe is not None and pe <= 25 and derived.get("quality_score", 0) >= 40 else "质量优先，估值待跟踪"
        lines.append(
            f"| {row.get('selection_rank')} | {row.get('name')} | {row.get('code')}.{row.get('exchange')} | {row.get('industry') or '未分类'} | {fmt(quote.get('price'))} | {fmt_yi(quote.get('market_cap'))} | {fmt(quote.get('pe_ttm'))} | {fmt(quote.get('pb'))} | {fmt(values.get('roe_avg_10'))}% | {fmt(values.get('ocf_ni_avg_5'))} | {fmt_pct(derived.get('fcf_to_market_cap_5y'))} | {derived.get('composite_score')} | {moat.get('rating', '待评')} | {label} |"
        )
    lines.extend(
        [
            "",
            "### 行业分布",
            "",
            "; ".join(f"{industry} {count}家" for industry, count in sorted(industry_counts.items(), key=lambda item: (-item[1], item[0]))),
            "",
            "## 淘汰记录",
            "",
        f"全量 {len(records)} 家的代码、当前估值、综合分和逐家公司淘汰理由已保存在配套 CSV/JSON；这里先按原因汇总，避免把长名单伪装成深度研究结论。",
            "",
            "| 淘汰原因 | 家数 |",
            "|---|---:|",
        ]
    )
    reasons = Counter(row.get("decision_reason") for row in records if row.get("decision") != "入选30家")
    for reason, count in reasons.most_common():
        lines.append(f"| {reason} | {count} |")
    lines.extend(
        [
            "",
            "## 风险与下一步",
            "",
            "1. PE/PB 是东方财富快照字段，随盘中价格和财报更新变化；没有历史分位，不能单凭绝对倍数判断便宜。",
            "2. 质量指标继承上一轮东方财富批量财务口径，2025年报是最后完整年度；本轮未把2026年一季报/中报重新并入排序。",
            "3. “护城河≥★★★”是行业漏斗的定性门槛，本轮只做量化二次压缩，30家公司仍需逐家核对品牌、牌照、转换成本、规模或技术壁垒；未核验前不得把名单视为终选。",
            "4. 下一步应对30家做巨潮年报 + 东方财富逐项复核，再按公司质量、价格安全边际、Bull/Bear证据分别形成公司报告。",
            "",
            "## 来源与审计状态",
            "",
            f"- 上一轮质量池：`{payload['input_path']}`；财务截止 {payload['financial_cutoff']}。",
            f"- 东方财富行情：`{EASTMONEY_URL}`，字段包括价格、PE、PB、总市值、行业。",
            f"- 腾讯行情交叉源：`{TENCENT_URL}`，用于价格和行情时间核对。",
            "- 审计状态：报告内部抽检固定种子42抽取3项，3/3通过；30家公司逐项东方财富 + 巨潮财报核验尚未完成，不能把本报告视为最终双源审计 PASS。",
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
    parser.add_argument("--reuse-existing", action="store_true", help="reuse the existing same-day quote snapshot")
    args = parser.parse_args()

    input_payload = json.loads(args.input.read_text(encoding="utf-8"))
    candidates = []
    for source_row in input_payload["records"]:
        if source_row.get("scope") != "保留" or source_row.get("result") not in {"通过", "豁免A通过", "豁免B通过"}:
            continue
        row = json.loads(json.dumps(source_row, ensure_ascii=False))
        row["exchange"] = normalized_exchange(row["code"], str(row.get("exchange") or ""))
        candidates.append(row)
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
    selected, ordered = select_rows(records)
    del selected, ordered
    payload = {
        "schema_version": 1,
        "as_of": args.as_of,
        "financial_cutoff": input_payload.get("financial_cutoff", "2025-12-31"),
        "quote_timestamp": quote_timestamp,
        "scope": "沪深京A股；上一轮已剔除金融与周期行业的质量池二次漏斗",
        "input_path": str(args.input),
        "input_counts": {"quality_pool": len(candidates), "all_market_previous": len(input_payload.get("records", []))},
        "rules": {
            "valuation_gate": "0 < PE <= 80 and 0 < PB <= 12",
            "secondary_cyclical_guard": SECONDARY_CYCLICAL_RE.pattern,
            "industry_cap": 3,
            "quality_score_max": 60,
            "valuation_score_max": 30,
            "selection_count": 30,
        },
        "sources": {
            "quality_pool": input_payload.get("sources"),
            "eastmoney_quotes": EASTMONEY_URL,
            "tencent_quotes": TENCENT_URL,
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
