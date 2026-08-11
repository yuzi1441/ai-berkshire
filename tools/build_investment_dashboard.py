#!/usr/bin/env python3
"""Build an auditable Obsidian decision table and static dashboard data.

The builder reads Markdown reports without changing them. It ranks conclusions
only by an explicit report data cutoff, never by filesystem modification time.
When the selected newest conclusion has no buy price, the output deliberately
shows ``价格未给出`` instead of carrying an older value forward.

Only individual company equities are published to the decision board. Industry,
theme, comparison, and screening reports stay in the library catalog only.
Each company also keeps a historical report-conclusion trail from prior company research.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIRECTORY = ROOT / "reports"
DATA_DIRECTORY = ROOT / "data" / "investment-dashboard"
SITE_DIRECTORY = ROOT / "site"
REGISTRY_PATH = ROOT / "data" / "report-routing" / "company_registry.json"
OVERRIDES_PATH = DATA_DIRECTORY / "overrides.json"
SKIPPED_PATH_PARTS = {"00-index", "_inbox", "_scripts", "_templates", "sources", "source_docs"}
TOPIC_DIRECTORIES = {
    "AI产业研究",
    "AI高速互联PCB材料",
    "AI高速互联PCB材料层",
    "A股低估行业",
    "A股适合投资行业",
    "A股行业投资前景筛选",
    "A股大型变压器",
    "AI基建-光通信与存储-20260512",
    "bottleneck-map",
    "白酒周期",
    "巴菲特镜子测试",
    "晨星估值筛选",
    "晨星深度低估",
    "存储半导体",
    "当前市场投资方向",
    "电力与资源",
    "电力设备六赛道二次筛选",
    "读书与播客",
    "段永平",
    "段永平vs李录",
    "李录",
    "公众号",
    "宏观利率",
    "换仓决策",
    "净现金折价股-全市场-20260417",
    "科创板召回池",
    "破净&晨星潜在涨幅高",
    "筛选公司",
    "数据中心电气瓶颈",
    "存储",
    "召回池",
    "主题文章",
    "中国汽车市场",
    "多公司对比",
    "港股召回池",
    "美股召回池",
    "行业研究",
    "国防含能材料-民爆-防务材料链",
    "半导体设备材料国产化",
    "大型变压器",
    "血液制品",
    "Token中转站",
    "Temu",
    "NASDAQ-100",
}
INDUSTRY_NAME_MARKERS = (
    "行业",
    "产业链",
    "产业研究",
    "产业全景",
    "赛道",
    "漏斗",
    "筛选",
    "对比",
    "全景",
    "指数",
    "召回池",
    "行业研究",
)
INDUSTRY_PATH_MARKERS = (
    "industry",
    "industry-research",
    "funnel",
    "对比",
    "行业",
    "产业链",
)
DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})(?:日)?")
TICKER_PATTERN = re.compile(r"(?i)(?<!\d)(\d{6}\.(?:SH|SZ|BJ)|\d{4,5}\.HK)(?!\d)")
SIX_DIGIT_TICKER_PATTERN = re.compile(r"(?:股票|证券)代码[^\n|]{0,24}?(?<!\d)(\d{6})(?!\d)")
DECISION_MARKERS = ("最终决策", "最终建议", "最终投资建议", "明确结论", "投资建议", "综合结论", "行动建议", "行动清单", "操作建议", "分层操作建议", "分层价格区间", "一句话投资判断", "买入前 Checklist", "买入前Checklist")
DECISION_CONTRACT_HEADING = "看板决策契约"
DECISION_CONTRACT_VERSION = "1"
DECISION_CONTRACT_FIELDS = (
    "契约版本",
    "报告类型",
    "公司",
    "股票代码",
    "市场",
    "报告日期",
    "数据截止日",
    "基本面建议动作",
    "结论摘要",
    "激进型动作",
    "激进型价格区间",
    "稳健型动作",
    "稳健型价格区间",
    "保守型动作",
    "保守型价格区间",
    "买入失效条件",
    "下次复核日期",
    "研究置信度",
)
DECISION_CONTRACT_ACTIONS = {"买入", "分批买入", "持有", "观察", "减仓/卖出", "待复核"}
DECISION_CONTRACT_MARKETS = {"A股", "港股", "美股", "未识别"}
DECISION_CONTRACT_NULL_VALUES = {"", "-", "--", "无", "不适用", "未给出", "待复核"}
PRICE_PATTERN = re.compile(
    r"(?P<operator>≤|<=|<|低于|以下|跌至|回落至|约)?\s*"
    r"(?P<currency>HK\$|HKD|RMB|CNY|US\$|USD|\$)?\s*"
    r"(?P<first>\d+(?:\.\d+)?)\s*"
    r"(?:[—–-]\s*(?P<second>\d+(?:\.\d+)?))?\s*"
    r"(?P<unit>元|港元|美元)?",
    flags=re.IGNORECASE,
)


def clean_markdown(value: str) -> str:
    """Turn a short Markdown fragment into compact dashboard text."""
    value = re.sub(r"!?(?:\[[^\]]*\]\([^)]*\))", "", value)
    # Keep comparison operators used by price bands; only strip Markdown emphasis.
    value = re.sub(r"[`*_#]", "", value)
    value = value.replace("|", " ")
    return re.sub(r"\s+", " ", value).strip()


def parse_date(text: str) -> str | None:
    """Return an ISO date from the first supported Chinese or ISO date string."""
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return None


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    """Load a JSON object or return the supplied default when it is absent."""
    if not path.is_file():
        return default
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def load_registry(path: Path) -> list[dict[str, Any]]:
    """Load valid company registry entries for canonical-name lookup."""
    payload = load_json(path, {"companies": []})
    companies = payload.get("companies", [])
    return companies if isinstance(companies, list) else []


def normalize_text(value: str) -> str:
    """Normalize user-visible names for exact alias matching."""
    return re.sub(r"[\s_-]+", "", value).casefold()


def registry_company(
    registry: list[dict[str, Any]], company: str, ticker: str | None
) -> dict[str, Any] | None:
    """Resolve an entity through exact ticker or configured aliases."""
    ticker_key = (ticker or "").upper()
    name_key = normalize_text(company)
    for entry in registry:
        tickers = {str(item).upper() for item in entry.get("tickers", [])}
        aliases = [entry.get("canonical_name", ""), *entry.get("aliases", [])]
        if ticker_key and ticker_key in tickers:
            return entry
        if name_key and name_key in {normalize_text(str(alias)) for alias in aliases}:
            return entry
    return None


def extract_data_cutoff(lines: list[str]) -> str | None:
    """Extract the latest explicitly labelled data cutoff from a report.

    Only labelled lines are considered. A filename date and filesystem timestamp
    are intentionally ignored because neither is a report data cutoff.
    """
    primary_labels = (
        "数据截止",
        "数据截至",
        "截止日期",
        "data cutoff",
        "as of",
        "股价截至",
        "行情基准",
    )
    secondary_labels = ("报告日期", "研究日期", "撰写日期")
    primary: list[str] = []
    secondary: list[str] = []
    for index, line in enumerate(lines[:120]):
        folded = line.casefold()
        labels = primary_labels if any(label in folded for label in primary_labels) else (
            secondary_labels if any(label in folded for label in secondary_labels) else ()
        )
        if not labels:
            continue
        bucket = primary if labels is primary_labels else secondary
        # A labelled cutoff line may also state the later report completion date.
        # The first date is the one attached to the cutoff / market-benchmark label.
        match = DATE_PATTERN.search(line)
        if match:
            parsed = parse_date(match.group(0))
            if parsed:
                bucket.append(parsed)
    if primary:
        return max(primary)
    return max(secondary) if secondary else None


def parse_frontmatter(lines: list[str]) -> dict[str, str]:
    """Parse the small YAML frontmatter subset used by generated reports."""
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:80]:
        if line.strip() == "---":
            return values
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[match.group(1)] = value
    return {}


def frontmatter_date(value: str | None) -> str | None:
    """Validate a frontmatter date without falling back to filename timestamps."""
    return parse_date(value or "")


def extract_technical_lights(lines: list[str]) -> list[dict[str, str]]:
    """Extract the fixed four-row trend-light table from a technical report."""
    start = next(
        (index for index, line in enumerate(lines) if re.sub(r"[#*\s]", "", line).startswith("三盏趋势灯")),
        None,
    )
    if start is None:
        return []
    lights: list[dict[str, str]] = []
    for line in lines[start + 1 : start + 24]:
        if not line.lstrip().startswith("|"):
            if lights:
                break
            continue
        cells = [clean_markdown(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[0] in {"观察维度", "---"} or re.fullmatch(r":?-{3,}:?", cells[0]):
            continue
        signal = cells[1].replace("信号", "").strip()
        if signal not in {"绿", "黄", "红"}:
            continue
        lights.append({"dimension": cells[0], "light": signal, "meaning": cells[2]})
    return lights


def technical_snapshot(report_path: Path, repo_root: Path, registry: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Read a technical report as an auxiliary snapshot, never a decision candidate."""
    text = report_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    frontmatter = parse_frontmatter(lines)
    if frontmatter.get("type") != "technical-analysis":
        return None
    company = normalize_company_name(frontmatter.get("company", ""))
    ticker = (frontmatter.get("ticker") or "").upper() or None
    registry_entry = registry_company(registry, company, ticker)
    if registry_entry:
        company = str(registry_entry["canonical_name"])
    analysis_date = frontmatter_date(frontmatter.get("analysis_date"))
    data_cutoff = frontmatter_date(frontmatter.get("data_cutoff"))
    lights = extract_technical_lights(lines)
    required_dimensions = {"短期（20日）", "中期（60日）", "长期（200日）", "量能确认"}
    light_dimensions = {item["dimension"] for item in lights}
    try:
        latest_price = float(frontmatter["latest_price"])
    except (KeyError, ValueError):
        latest_price = None
    publishable = frontmatter.get("publishable", "").casefold() == "true"
    display_complete = bool(
        company
        and analysis_date
        and data_cutoff
        and frontmatter.get("technical_state")
        and frontmatter.get("preferred_observation_zone")
        and latest_price is not None
        and required_dimensions <= light_dimensions
    )
    return {
        "company": company,
        "ticker": ticker,
        "status": "ready" if publishable and display_complete else "review",
        "report_path": report_path.relative_to(repo_root).as_posix(),
        "analysis_date": analysis_date,
        "data_cutoff": data_cutoff,
        "state": frontmatter.get("technical_state") or "待复核",
        "confidence": frontmatter.get("technical_confidence") or "待复核",
        "publishable": publishable,
        "latest_price": latest_price,
        "currency": frontmatter.get("currency") or None,
        "observation_zone": frontmatter.get("preferred_observation_zone") or None,
        "fundamental_entry_plan": frontmatter.get("fundamental_entry_plan") or None,
        "combined_candidate_zone": frontmatter.get("combined_candidate_zone") or None,
        "valid_buy_candidate": frontmatter.get("valid_buy_candidate") or None,
        "lights": lights,
    }


def technical_snapshot_rank(snapshot: dict[str, Any]) -> tuple[str, str, str]:
    """Rank technical snapshots only by their explicit market and analysis dates."""
    return (
        snapshot.get("data_cutoff") or "0000-00-00",
        snapshot.get("analysis_date") or "0000-00-00",
        snapshot.get("report_path") or "",
    )


def attach_technical_snapshots(
    decisions: list[dict[str, Any]], snapshots: list[dict[str, Any]]
) -> None:
    """Attach one latest technical snapshot without changing fundamental decisions."""
    by_ticker: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    by_company_without_ticker: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.get("ticker"):
            by_ticker[str(snapshot["ticker"])].append(snapshot)
        elif snapshot.get("company"):
            by_company_without_ticker[str(snapshot["company"])].append(snapshot)

    for decision in decisions:
        ticker = str(decision.get("ticker") or "").upper()
        candidates = by_ticker.get(ticker, []) if ticker else by_company_without_ticker.get(str(decision["company"]), [])
        if not candidates:
            # Canonical-name matching is only a fallback when the technical report has no ticker.
            candidates = by_company_without_ticker.get(str(decision["company"]), [])
        if candidates:
            decision["technical_analysis"] = max(candidates, key=technical_snapshot_rank).copy()
        else:
            decision["technical_analysis"] = {"status": "missing", "lights": []}


def extract_report_completed_date(lines: list[str]) -> str | None:
    """Extract an explicitly labelled report completion date for tie-breaking.

    This is intentionally separate from the data cutoff. It is only used when
    two reports cover the same data date, so newer completed research can
    supersede an earlier tracking note without relying on file timestamps.
    """
    labels = ("报告完成日", "报告完成日期", "研究完成日", "完成日期", "建立日期", "撰写日期")
    dates: list[str] = []
    for line in lines[:120]:
        folded = line.casefold()
        for label in labels:
            start = folded.find(label)
            if start < 0:
                continue
            match = DATE_PATTERN.search(line[start + len(label) :])
            if not match:
                continue
            parsed = parse_date(match.group(0))
            if parsed:
                dates.append(parsed)
    return max(dates) if dates else None


def extract_ticker(text: str) -> str | None:
    """Extract a standard A-share, Beijing-board, or Hong Kong ticker."""
    match = TICKER_PATTERN.search(text)
    if match:
        ticker = match.group(1).upper()
        return f"{ticker.zfill(8)[:-3]}.HK" if ticker.endswith(".HK") and len(ticker) < 8 else ticker
    match = SIX_DIGIT_TICKER_PATTERN.search(text)
    if match:
        code = match.group(1)
        return f"{code}.SH" if code.startswith(("6", "9")) else f"{code}.SZ"
    return None


def market_for_ticker(ticker: str | None, market_hint: str | None = None) -> str:
    """Return a display market, prioritizing an explicit ticker suffix."""
    if ticker and ticker.endswith(".HK"):
        return "港股"
    if ticker and ticker.endswith((".SH", ".SZ", ".BJ")):
        return "A股"
    return market_hint or "未识别"


def extract_title(lines: list[str], fallback: str) -> str:
    """Use the first H1 heading as a report title when available."""
    for line in lines[:80]:
        if line.startswith("# "):
            return clean_markdown(line[2:]) or fallback
    return fallback


def decision_section(lines: list[str]) -> list[str]:
    """Return the most decision-specific report section, if one exists."""
    starts: list[int] = []
    for index, line in enumerate(lines):
        if (
            line.lstrip().startswith("#")
            and DECISION_CONTRACT_HEADING not in line
            and any(marker in line for marker in DECISION_MARKERS)
        ):
            starts.append(index)
    if starts:
        start = starts[-1]
        end = min(len(lines), start + 48)
        for index in range(start + 1, min(len(lines), start + 48)):
            if index > start + 2 and lines[index].startswith("## "):
                end = index
                break
        return lines[start:end]

    for index, line in enumerate(lines[:100]):
        if "一句话投资判断" in line:
            return lines[index : min(len(lines), index + 20)]
    return []


def _action_from_blob(blob: str) -> str | None:
    """Map one focused decision blob to a coarse action label.

    Priority favors the explicit stance (观望/回避/不追) over nested price-band
    language such as "到 XX 元再分批建仓", which previously caused false 分批买入.
    """
    text = clean_markdown(blob)
    if not text:
        return None
    # Ignore pure signal-table headers that are not the stance itself.
    if re.fullmatch(r"(卖出信号|加仓信号|买入信号|风险信号)", text):
        return None

    if re.search(
        r"坚决回避|明确回避|当前回避|回避当前|不建议买入|不宜买入|不要买入|"
        r"暂不买入|先不买入|远离|坚决不买|不要追",
        text,
    ):
        return "观察"
    # Dual stance common in team reports: holders hold, new money does not chase.
    if re.search(r"持有\s*[/、]\s*观望|持有或观望|观望\s*[/、]\s*持有", text):
        return "持有"
    if re.search(r"不追高|不追价|不追", text) and not re.search(r"持有", text):
        return "观察"
    if re.search(
        r"立即卖出|大幅减仓|建议卖出|建议减仓|进入.{0,8}减仓|减仓观察|考虑减仓|清仓|锁定利润",
        text,
    ) and not re.search(r"卖出信号|加仓信号|离场信号|减仓信号", text):
        return "减仓/卖出"
    if re.search(
        r"观望为主|继续观察|保持观望|建议观望|观望|等待更好|等待.{0,8}买点|"
        r"放入观察|只观察|暂观望|先观望|等待基本面|等待验证",
        text,
    ):
        return "观察"
    if re.search(r"持有但不加|持有[/\s、与和]*观望|继续持有(?!.*买入)|持有观望", text):
        return "持有"
    if re.search(r"强烈买入|积极买入|重点买入", text) and not re.search(r"观望|等待|回避|不追", text):
        return "买入"
    if re.search(
        r"小额分批买入|分批买入|分批建仓|可开始.{0,8}买入|开始建仓|可建仓|适度建仓|"
        r"建议.{0,6}买入|可以买入|可配置|可研究分批",
        text,
    ) and not re.search(r"观望为主|等待更好|回避|不追|等待.{0,8}买点", text):
        return "分批买入"
    if re.search(r"持有", text) and not re.search(r"买入|建仓", text):
        return "持有"
    if re.search(r"观察|等待", text):
        return "观察"
    return None


def classify_action(section: list[str]) -> str:
    """Classify the dominant action in a decision section conservatively.

    Prefer explicit conclusion lines and the 空仓者 (new-money) stance. Nested
    "到某价格再分批" language must not override a primary 观望/回避 conclusion.
    """
    text = "\n".join(section)

    # 1) Explicit conclusion sentences.
    conclusion_pattern = (
        r"(?:明确结论|一句话投资判断|综合结论|最终结论|结论)[：:\s]*\**([^\n]{4,240})"
    )
    for match in re.finditer(conclusion_pattern, text):
        hit = _action_from_blob(match.group(1))
        if hit:
            return hit

    # 2) 空仓者 guidance in Markdown tables or prose.
    empty_blobs: list[str] = []
    table_pattern = r"空仓者[^\n|]{0,16}\|\s*\**([^\n|]{4,280})"
    prose_pattern = r"空仓者[：:\s]+([^\n]{4,240})"
    for match in re.finditer(table_pattern, text):
        empty_blobs.append(match.group(1))
    for match in re.finditer(prose_pattern, text):
        empty_blobs.append(match.group(1))
    for blob in empty_blobs:
        hit = _action_from_blob(blob)
        if hit:
            return hit

    # 3) Whole decision section with the same conservative priority.
    hit = _action_from_blob(text)
    if hit:
        return hit
    if re.search(
        r"立即卖出|大幅减仓|建议卖出|建议减仓|进入.{0,8}减仓|减仓观察|考虑减仓|清仓",
        text,
    ) and not re.search(r"卖出信号|加仓信号|离场信号|减仓信号", text):
        return "减仓/卖出"
    return "未提取"


def extract_summary(section: list[str]) -> str:
    """Extract a readable decision summary from a selected section."""
    preferred = [
        line
        for line in section
        if any(marker in line for marker in ("明确结论", "一句话投资判断", "空仓者", "投资建议"))
    ]
    for line in [*preferred, *section]:
        summary = clean_markdown(line)
        has_explicit_action = len(summary) >= 8 and re.search(
            r"观察|等待|买入|建仓|持有|减仓|卖出|不追",
            summary,
        )
        if (len(summary) >= 16 or has_explicit_action) and not re.fullmatch(r"[-:| ]+", summary):
            return summary[:360]
    return "未提取到可供看板展示的结论。"


def format_price_match(match: re.Match[str]) -> str | None:
    """Convert a PRICE_PATTERN match into a display string with unit or currency."""
    currency = (match.group("currency") or "").upper()
    unit = match.group("unit") or ""
    if not currency and not unit:
        return None
    if currency in {"HK$", "HKD"} or unit == "港元":
        prefix = "HK$"
    elif currency in {"US$", "USD", "$"} or unit == "美元":
        prefix = "US$"
    else:
        prefix = ""
    value = match.group("first")
    if match.group("second"):
        value = f"{value}-{match.group('second')}"
    operator = match.group("operator") or ""
    return f"{operator}{prefix}{value}{'' if prefix else ' 元'}"


def extract_buy_price(section: list[str]) -> str | None:
    """Extract the best-supported buy or add position price from a conclusion.

    Price candidates must contain an explicit unit or currency. This prevents a
    report year, P/E ratio, or other bare number from becoming a false price.
    """
    candidates: list[tuple[int, str]] = []
    action_line = re.compile(
        r"买入|建仓|加仓|空仓|观察名单|等待|回落至|跌至|低于|优先|稳健|激进|保守|安全边际|价格区间|目标价|合理价"
    )
    for line in section:
        if not action_line.search(line):
            continue
        # Parenthetical PE-linked bands: PE 12-13x（约20-23元）
        for pe_match in re.finditer(
            r"(?:PE|市盈率).{0,40}?(?:约)?\s*(\d+(?:\.\d+)?)\s*[-—~至到]\s*(\d+(?:\.\d+)?)\s*元",
            line,
            flags=re.I,
        ):
            display = f"{pe_match.group(1)}-{pe_match.group(2)} 元"
            score = 55
            if re.search(r"建仓|买入", line):
                score += 20
            candidates.append((score, display))
        for match in PRICE_PATTERN.finditer(line):
            # Do not truncate commodity quotes such as "$13,595/吨" into a
            # synthetic "$13" stock-price anchor.
            if re.match(r",\d{3}", line[match.end() :]):
                continue
            display = format_price_match(match)
            if not display:
                continue
            score = 0
            if re.search(r"买入|建仓", line):
                score += 50
            if re.search(r"等待|观察名单|轻仓观察", line):
                score += 40
            if "加仓" in line:
                score += 35
            if "空仓" in line:
                score += 20
            if "目标价" in line and not re.search(r"买入|建仓|等待", line):
                score += 15
            if "当前股价" in line and not re.search(r"买入|建仓", line):
                score -= 30
            if re.search(r"市值|营收|净利润|亿元", line) and "元" in display:
                if "亿" in line[max(0, match.start() - 6): match.end() + 6]:
                    continue
            if re.fullmatch(r"(?:≤|≥|<|>|低于|高于)?\s*20\d{2}\s*元?", display):
                continue
            candidates.append((score, display))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def markdown_cells(line: str) -> list[str] | None:
    """Return cells from one ordinary Markdown table row, excluding separators."""
    stripped = line.strip()
    if not stripped.startswith("|") or stripped.count("|") < 2:
        return None
    cells = [clean_markdown(cell) for cell in stripped.strip("|").split("|")]
    if all(re.fullmatch(r"[: -]*", cell) for cell in cells):
        return None
    return cells


def is_contract_null(value: str | None) -> bool:
    """Return whether a contract cell intentionally carries no usable value."""
    return clean_markdown(value or "") in DECISION_CONTRACT_NULL_VALUES


def contract_ticker(value: str) -> str | None:
    """Normalize a contract ticker while retaining plain US ticker symbols."""
    if is_contract_null(value):
        return None
    parsed = extract_ticker(f"股票代码：{value}")
    if parsed:
        return parsed
    text = clean_markdown(value).upper()
    return text if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", text) else None


def extract_decision_contract(lines: list[str]) -> dict[str, Any] | None:
    """Read one complete, validated dashboard contract from a report.

    Contracts are deliberately strict. A malformed or incomplete one is ignored
    so legacy natural-language extraction remains the safe compatibility path.
    """
    headings = [
        index
        for index, line in enumerate(lines)
        if line.lstrip().startswith("#") and DECISION_CONTRACT_HEADING in line
    ]
    if not headings:
        return None

    for heading_index in reversed(headings):
        values: dict[str, str] = {}
        table_started = False
        for index in range(heading_index + 1, min(len(lines), heading_index + 48)):
            cells = markdown_cells(lines[index])
            if cells is None:
                if table_started:
                    if lines[index].lstrip().startswith("|"):
                        # Markdown table separators are intentionally filtered by
                        # markdown_cells; they do not end the contract table.
                        continue
                    break
                continue
            if len(cells) < 2:
                continue
            if cells[0] == "字段" and cells[1] in {"内容", "值"}:
                table_started = True
                continue
            if not table_started:
                continue
            field, value = cells[0], cells[1]
            if field not in DECISION_CONTRACT_FIELDS or field in values:
                return None
            values[field] = value

        if set(values) != set(DECISION_CONTRACT_FIELDS):
            continue
        if values["契约版本"] != DECISION_CONTRACT_VERSION:
            continue
        if values["报告类型"] not in {"company-fundamental", "company-checklist"}:
            continue
        company = clean_markdown(values["公司"])
        summary = clean_markdown(values["结论摘要"])
        report_completed_at = None if is_contract_null(values["报告日期"]) else parse_date(values["报告日期"])
        data_cutoff = None if is_contract_null(values["数据截止日"]) else parse_date(values["数据截止日"])
        action = clean_markdown(values["基本面建议动作"])
        if (
            not company
            or is_contract_null(company)
            or (not is_contract_null(values["报告日期"]) and not report_completed_at)
            or (not is_contract_null(values["数据截止日"]) and not data_cutoff)
            or action not in DECISION_CONTRACT_ACTIONS
        ):
            continue
        if is_contract_null(summary):
            summary = ""
        market = clean_markdown(values["市场"])
        if not is_contract_null(market) and market not in DECISION_CONTRACT_MARKETS:
            continue
        confidence = clean_markdown(values["研究置信度"])
        if confidence not in {"高", "中", "低", "待复核"}:
            continue

        stances: list[dict[str, str]] = []
        for stance in ("激进型", "稳健型", "保守型"):
            stance_action = clean_markdown(values[f"{stance}动作"])
            price_range = clean_markdown(values[f"{stance}价格区间"])
            if is_contract_null(stance_action) and is_contract_null(price_range):
                continue
            if is_contract_null(stance_action):
                return None
            item = {"stance": stance, "action": stance_action}
            if not is_contract_null(price_range):
                item["price_range"] = price_range
            stances.append(item)

        return {
            "version": DECISION_CONTRACT_VERSION,
            "report_type": values["报告类型"],
            "company": company,
            "ticker": contract_ticker(values["股票代码"]),
            "market": None if is_contract_null(market) else market,
            "report_completed_at": report_completed_at,
            "data_cutoff": data_cutoff,
            "action": action,
            "summary": summary or None,
            "investor_stances": stances,
            "invalidation_triggers": clean_markdown(values["买入失效条件"]),
            "next_review_date": parse_date(values["下次复核日期"]),
            "confidence": confidence,
        }
    return None


CHECKLIST_GATE_NAMES = (
    ("能力圈", ("能力圈", "生意是否容易理解", "生意能否理解")),
    ("好生意", ("好生意", "经济特征")),
    ("护城河", ("护城河", "竞争优势")),
    ("管理层", ("管理层", "人的因素")),
    ("安全边际", ("安全边际", "价格是否足够便宜", "价格与安全边际")),
    ("仓位纪律", ("仓位纪律", "决策纪律")),
)

CHECKLIST_HEADING_PATTERN = re.compile(
    r"(?:巴菲特\s*)?(?:价值投资\s*)?买入前\s*checklist|"
    r"(?:巴菲特\s*)?checklist\s*(?:买入前)?",
    flags=re.IGNORECASE,
)


def checklist_gate_name(text: str) -> str | None:
    """Map a table label or nearby heading to one of the six standard gates."""
    for name, aliases in CHECKLIST_GATE_NAMES:
        if any(alias in text for alias in aliases):
            return name
    return None


def checklist_section(lines: list[str]) -> list[str] | None:
    """Return the latest explicitly headed Checklist section from a report."""
    starts: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("#") or not CHECKLIST_HEADING_PATTERN.search(line):
            continue
        level = heading_level(line) or 2
        starts.append((index, level))
    if not starts:
        return None
    start, level = starts[-1]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        next_level = heading_level(lines[index])
        if next_level is not None and next_level <= level:
            end = index
            break
    section = lines[start:end]
    return section if len(section) >= 3 else None


def extract_checklist_summary(lines: list[str]) -> str:
    """Extract a concise conclusion from a legacy or embedded Checklist."""
    preferred_markers = (
        "最终判定",
        "总判定",
        "Checklist 结果",
        "Checklist结果",
        "Checklist 结论",
        "Checklist结论",
        "Checklist通过率",
        "Checklist通过",
        "灰色地带",
    )
    candidates = [
        clean_markdown(line)
        for line in lines
        if any(marker.casefold() in line.casefold() for marker in preferred_markers)
    ]
    for candidate in reversed(candidates):
        if len(candidate) >= 8:
            return candidate[:360]
    return ""


def extract_checklist_gates(lines: list[str]) -> list[dict[str, str]]:
    """Extract standard six-gate rows and legacy numbered Checklist rows."""
    gates: list[dict[str, str]] = []
    for line in lines:
        cells = markdown_cells(line)
        if not cells or len(cells) < 2:
            continue
        score_index = next(
            (
                index
                for index, cell in enumerate(cells)
                if re.fullmatch(r"[★☆]{1,5}", cell.replace(" ", ""))
            ),
            None,
        )
        if score_index is None:
            continue
        score = cells[score_index].replace(" ", "")
        label = " ".join(cells[:score_index]).strip()
        matched_name = checklist_gate_name(label)
        if not matched_name or any(item["name"] == matched_name for item in gates):
            continue
        result = clean_markdown(cells[score_index + 1]) if len(cells) > score_index + 1 else "待复核"
        reason = clean_markdown(cells[score_index + 2]) if len(cells) > score_index + 2 else ""
        gates.append({"name": matched_name, "score": score, "result": result, "reason": reason})

    # Some older reports put the score in prose below a gate heading instead of
    # in the summary table. Keep this conservative and only use the nearest
    # preceding gate heading, so unrelated stars in valuation text are ignored.
    if len(gates) < len(CHECKLIST_GATE_NAMES):
        for index, line in enumerate(lines):
            score_match = re.search(r"评分[：:]?\s*([★☆]{1,5})", line)
            if not score_match:
                continue
            nearby = " ".join(lines[max(0, index - 12) : index + 1])
            matched_name = checklist_gate_name(nearby)
            if not matched_name or any(item["name"] == matched_name for item in gates):
                continue
            result = "待复核"
            result_match = re.search(r"(?:评分[：:]?\s*[★☆]{1,5}[。；,，、\s]*)((?:不|未)?通过|灰色|条件通过|待验证)", line)
            if result_match:
                result = result_match.group(1)
            gates.append(
                {
                    "name": matched_name,
                    "score": score_match.group(1),
                    "result": result,
                    "reason": clean_markdown(line),
                }
            )

    # A number of legacy reports use a 10-item table without star scores. It is
    # still useful in the board as an auditable pre-buy check, so preserve those
    # rows as generic gates when no six-gate score table was found.
    if not gates:
        generic: list[dict[str, str]] = []
        for line in lines:
            cells = markdown_cells(line)
            if not cells or len(cells) < 3 or not re.fullmatch(r"\d+\.?", cells[0].strip()):
                continue
            label = clean_markdown(cells[1])
            if not label or label in {"检查项", "项目"}:
                continue
            result = clean_markdown(cells[2]) or "待复核"
            reason = clean_markdown(cells[3]) if len(cells) >= 4 else ""
            generic.append({"name": label, "score": "", "result": result, "reason": reason})
        gates = generic
    return gates


def extract_checklist_status(
    lines: list[str], contract: dict[str, Any], gates: list[dict[str, str]]
) -> dict[str, Any]:
    """Build a display-only Checklist summary without changing the main decision."""
    text = "\n".join(lines) + "\n" + str(contract.get("summary") or "")
    hard_veto = bool(
        re.search(r"(?<![未有不])触发硬性否决|硬性否决[：: ]{0,10}(?:已触发|[1-9]\s*项)", text)
    )
    summary_text = str(contract.get("summary") or "")
    if hard_veto:
        status = "否决"
    elif "灰色地带" in summary_text and not re.search(r"❌|否决|未通过\s*Checklist", summary_text):
        status = "灰色地带"
    elif re.search(r"未通过[^\n]{0,12}Checklist|Checklist[^\n]{0,25}(?:未通过|不通过)", summary_text):
        status = "未通过"
    elif "灰色地带" in text:
        status = "灰色地带"
    elif re.search(r"未通过[^\n]{0,12}Checklist|Checklist[^\n]{0,25}(?:未通过|不通过)", text):
        status = "未通过"
    elif re.search(r"通过[^\n]{0,25}Checklist|Checklist[^\n]{0,25}通过", text):
        status = "通过"
    else:
        status = "待复核"

    ratio_matches = [
        match
        for line in lines
        if re.search(r"Checklist|判定|结论|通过率", line, flags=re.IGNORECASE)
        for match in re.finditer(r"(?<!\d)(\d+)\s*/\s*(6|10)(?!\d)", line)
    ]
    passed_match = ratio_matches[-1] if ratio_matches else None
    passed_count = int(passed_match.group(1)) if passed_match else None
    total_gates = int(passed_match.group(2)) if passed_match else (len(gates) or 6)
    if passed_count is None:
        passed_count = sum(
            1
            for gate in gates
            if re.search(r"(?:通过|基本是|^是$|✅)", gate["result"])
            and not re.search(r"不通过|未通过|否", gate["result"])
        ) or None
    mirror_match = re.search(r"镜子测试[：:]?\s*(通过|未通过|不通过)", text)
    mirror_status = mirror_match.group(1) if mirror_match else "待复核"
    return {
        "status": status,
        "passed_count": passed_count,
        "total_gates": total_gates,
        "gates": gates,
        "hard_veto": hard_veto,
        "hard_veto_label": "已触发" if hard_veto else "未触发/未发现",
        "mirror_test": mirror_status,
        "action": contract.get("action") or "待复核",
        "summary": contract.get("summary") or "",
        "data_cutoff": contract.get("data_cutoff"),
        "report_date": contract.get("report_completed_at"),
        "next_review_date": contract.get("next_review_date"),
        "confidence": contract.get("confidence") or "待复核",
        "invalidation_triggers": contract.get("invalidation_triggers") or "",
    }


def checklist_record(
    report_path: Path, repo_root: Path, registry: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Read standalone or embedded Checklist content as an auxiliary layer."""
    text = report_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    relative = report_path.relative_to(repo_root)
    if any(part in SKIPPED_PATH_PARTS for part in relative.parts):
        return None
    path_company, entity_kind, path_market, _ = entity_from_path(relative)
    if entity_kind != "company" or re.search(r"多公司|对比|筛选|行业", path_company):
        return None

    contract = extract_decision_contract(lines)
    is_standalone = bool(re.search(r"checklist", report_path.stem, flags=re.IGNORECASE))
    section = checklist_section(lines)
    if contract and contract.get("report_type") == "company-checklist":
        checklist_lines = lines
        source_type = "standalone"
    elif is_standalone:
        checklist_lines = lines
        source_type = "standalone"
    elif section:
        checklist_lines = section
        source_type = "embedded"
    else:
        return None

    gates = extract_checklist_gates(checklist_lines)
    summary = extract_checklist_summary(checklist_lines)
    if not gates and not summary:
        return None

    metadata_contract = contract if contract and contract.get("report_type") == "company-checklist" else None
    company = normalize_company_name(str((contract or {}).get("company") or path_company))
    ticker = (contract or {}).get("ticker") or extract_ticker("\n".join(lines[:180]))
    registry_entry = registry_company(registry, company, ticker)
    if registry_entry:
        company = str(registry_entry["canonical_name"])
    market = (contract or {}).get("market") or market_for_ticker(ticker, path_market)
    data_cutoff = (contract or {}).get("data_cutoff") or extract_data_cutoff(lines)
    report_date = (contract or {}).get("report_completed_at") or extract_report_completed_date(lines)
    checklist_contract = metadata_contract or {
        "report_type": "embedded-checklist" if source_type == "embedded" else "legacy-checklist",
        "company": company,
        "ticker": ticker,
        "market": market,
        "data_cutoff": data_cutoff,
        "report_completed_at": report_date,
        "action": "待复核",
        "summary": summary or None,
        "confidence": "待复核",
        "invalidation_triggers": "",
        "next_review_date": None,
    }
    if not checklist_contract.get("summary") and summary:
        checklist_contract["summary"] = summary
    status = extract_checklist_status(checklist_lines, checklist_contract, gates)
    if summary and not status.get("summary"):
        status["summary"] = summary
    return {
        "company": company,
        "ticker": ticker,
        "market": market,
        "report_path": relative.as_posix(),
        "report_link": relative.as_posix(),
        "title": extract_title(lines, report_path.stem),
        "source_type": source_type,
        "decision_contract": metadata_contract,
        **status,
    }


def checklist_rank(record: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        record.get("data_cutoff") or "0000-00-00",
        record.get("report_date") or "0000-00-00",
        1 if record.get("source_type") == "standalone" else 0,
        record.get("report_path") or "",
    )


def attach_checklists(
    decisions: list[dict[str, Any]], records: list[dict[str, Any]]
) -> None:
    """Attach the latest Checklist and its compact history by canonical company."""
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["company"])].append(record)
    for decision in decisions:
        candidates = grouped.get(str(decision["company"]), [])
        if not candidates and decision.get("ticker"):
            candidates = [
                record for record in records if record.get("ticker") == decision.get("ticker")
            ]
        if not candidates:
            decision["checklist"] = {"status": "missing", "gates": [], "history": []}
            continue
        ordered = sorted(candidates, key=checklist_rank, reverse=True)
        latest = ordered[0].copy()
        latest["history"] = [
            {
                "status": item.get("status"),
                "action": item.get("action"),
                "data_cutoff": item.get("data_cutoff"),
                "report_date": item.get("report_date"),
                "report_path": item.get("report_path"),
                "report_link": item.get("report_link"),
                "source_type": item.get("source_type"),
            }
            for item in ordered
        ]
        decision["checklist"] = latest


def is_markdown_table_separator(line: str) -> bool:
    """Return True only for a Markdown table's header separator row."""
    stripped = line.strip()
    if not stripped.startswith("|") or stripped.count("|") < 2:
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def table_after_heading(
    lines: list[str], heading_terms: tuple[str, ...], required_headers: tuple[str, ...]
) -> tuple[list[str], list[list[str]]] | None:
    """Find a named Markdown table and return its headers plus body rows."""
    for heading_index, heading in enumerate(lines):
        if not all(term in heading for term in heading_terms):
            continue
        for index in range(heading_index + 1, min(len(lines), heading_index + 36)):
            headers = markdown_cells(lines[index])
            if (
                not headers
                or index + 1 >= len(lines)
                or not is_markdown_table_separator(lines[index + 1])
                or not all(any(term in header for header in headers) for term in required_headers)
            ):
                continue
            rows: list[list[str]] = []
            for row_index in range(index + 1, min(len(lines), index + 18)):
                row = markdown_cells(lines[row_index])
                if row is None:
                    if rows:
                        break
                    continue
                if len(row) == len(headers):
                    rows.append(row)
            return headers, rows
    return None


def header_index(headers: list[str], label: str) -> int | None:
    """Find a Markdown table column by a unique label fragment."""
    for index, header in enumerate(headers):
        if label in header:
            return index
    return None



def heading_level(line: str) -> int | None:
    """Return Markdown heading depth, or None when the line is not a heading."""
    match = re.match(r"^(#{1,6})\s+\S", line.strip())
    return len(match.group(1)) if match else None


def extract_valuation_section(lines: list[str]) -> dict[str, Any] | None:
    """Copy the report's valuation / margin-of-safety section verbatim.

    Strategy when the exact chapter boundary is ambiguous:
    1. Prefer standard titles such as ``估值与安全边际``.
    2. If only a nested subheading (e.g. 三情景估值) is found, expand upward to the
       nearest parent valuation chapter.
    3. Expand downward through related price/scenario/action tables until a clear
       non-valuation major section begins, so complete original tables are kept.
    """

    def heading_score(line: str, level: int) -> int:
        score = 0
        if re.search(r"估值与安全边际", line):
            score = 100
        elif re.search(r"财务质量与估值|估值与价格纪律", line):
            score = 90
        elif re.search(r"估值与行动|估值锚点|估值判断", line):
            score = 88
        elif re.search(r"最终决策与行动|最终决策|行动清单", line):
            # Many reports put action price bands in step 8; keep it eligible.
            score = 86
        elif re.search(r"最终投资建议|分层操作建议|分层价格区间", line):
            score = 82
        elif re.search(r"行动价格带|价格区间建议|合理价格区间|什么价位", line):
            score = 75
        elif re.search(r"三情景估值|情景估值|压力测试|反向估值", line):
            score = 68
        elif re.search(r"估值更新|估值复核", line):
            score = 58
        elif re.search(r"财务估值|估值基准|估值分析|估值", line) and level <= 3:
            score = 45 if re.search(r"财务估值|估值基准|估值分析", line) else 28
        # Nested tiny fragments should not outrank full chapters.
        if level >= 4:
            score = max(0, score - 15)
        return score

    def is_decision_action_heading(line: str) -> bool:
        """Step-8 style chapters that often hold the actionable price tables."""
        return bool(
            re.search(
                r"最终决策与行动|最终决策|行动清单|最终投资建议|最终建议|"
                r"操作建议|分层操作|行动价格|价格与动作|价格纪律",
                line,
            )
        )

    def is_related_valuation_heading(line: str) -> bool:
        if is_decision_action_heading(line):
            return True
        return bool(
            re.search(
                r"估值|安全边际|情景|价格带|价格区间|目标价|压力测试|反向估值|"
                r"分层操作|分层价格|行动价格|买入价|建仓|操作建议|合理价|"
                r"内在价值|对的价格|安全垫|第八步",
                line,
            )
        )

    def is_hard_stop_heading(line: str, level: int, start_level: int) -> bool:
        """Major sections that should end the valuation capture."""
        if level > start_level:
            return False
        # Decision/action chapters belong with valuation tables — never hard-stop.
        if is_decision_action_heading(line):
            return False
        # Same-or-higher level related valuation headings are continuations.
        if is_related_valuation_heading(line):
            return False
        if re.search(
            r"附录|数据来源|免责|Checklist|论文跟踪|新闻脉搏|下一步研究|"
            r"信息来源|参考资料|系列总结|研究框架|目录|风险矩阵|看多 vs|"
            r"第九步|第十步|第9部分|第10部分",
            line,
        ):
            return True
        # Bare "风险" section without valuation wording ends the capture.
        if re.search(r"风险", line) and not is_related_valuation_heading(line):
            return True
        # Generic next major step after decision chapter, without price content.
        if re.search(r"第[九九十\d]+[步部分章节]", line):
            return True
        if level <= start_level and not is_related_valuation_heading(line):
            return True
        return False

    scored: list[tuple[int, int, int, int, int]] = []
    for index, line in enumerate(lines):
        level = heading_level(line)
        if level is None:
            continue
        score = heading_score(line, level)
        if score:
            # Prefer higher score, shallower heading, earlier occurrence.
            scored.append((score, -level, -index, index, level))

    if not scored:
        # Fallback: locate first dense table near a valuation keyword paragraph.
        for index, line in enumerate(lines):
            if re.search(r"估值|安全边际|三情景|目标价", line) and index + 1 < len(lines):
                window = lines[index : min(len(lines), index + 80)]
                if any(row.strip().startswith("|") for row in window):
                    start = index
                    start_level = heading_level(line) or 2
                    scored.append((20, -start_level, -index, index, start_level))
                    break
    if not scored:
        return None

    best = max(scored)
    start = best[3]
    start_level = best[4]
    start_score = best[0]

    # Expand upward: nested 7.2 / 三情景 -> parent 第七步：估值与安全边际.
    if start_level >= 3 or start_score < 90:
        for index in range(start - 1, max(-1, start - 80), -1):
            level = heading_level(lines[index])
            if level is None:
                continue
            parent_score = heading_score(lines[index], level)
            if parent_score >= 88 and level < start_level:
                start = index
                start_level = level
                start_score = parent_score
                break
            # Stop climbing once we hit an unrelated major heading above.
            if level <= 2 and parent_score < 40 and not is_related_valuation_heading(lines[index]):
                break

    # Primary end: next hard-stop heading at same or higher level.
    end = len(lines)
    for index in range(start + 1, len(lines)):
        level = heading_level(lines[index])
        if level is None:
            continue
        if is_hard_stop_heading(lines[index], level, start_level):
            end = index
            break

    # If the captured body is still thin / table-less, keep absorbing following
    # related valuation blocks (price bands, scenarios, action tables).
    def body_has_table(a: int, b: int) -> bool:
        return any(line.strip().startswith("|") for line in lines[a:b])

    def body_quality(a: int, b: int) -> int:
        chunk = "\n".join(lines[a:b])
        quality = b - a
        if "|" in chunk:
            quality += 40
        if re.search(r"乐观|中性|悲观|激进|稳健|保守", chunk):
            quality += 20
        return quality

    guard = 0
    while end < len(lines) and guard < 12:
        guard += 1
        # Skip blanks
        cursor = end
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        if cursor >= len(lines):
            break
        level = heading_level(lines[cursor])
        if level is None:
            # Non-heading continuation; absorb a short prose/table run.
            run_end = cursor
            while run_end < len(lines) and heading_level(lines[run_end]) is None:
                run_end += 1
                if run_end - end > 120:
                    break
            if body_has_table(end, run_end) or body_quality(start, end) < 30:
                end = run_end
                continue
            break

        if is_hard_stop_heading(lines[cursor], level, start_level):
            break
        if not is_related_valuation_heading(lines[cursor]):
            # Allow one more same-level action/price section if current body lacks tables.
            if body_has_table(start, end) and body_quality(start, end) >= 50:
                break
            if not re.search(r"建议|操作|价格|仓位|买入|持有", lines[cursor]):
                break

        # Extend through this related subsection.
        next_end = len(lines)
        for index in range(cursor + 1, len(lines)):
            lvl = heading_level(lines[index])
            if lvl is not None and lvl <= level:
                if is_hard_stop_heading(lines[index], lvl, start_level):
                    next_end = index
                    break
                if lvl < level:
                    next_end = index
                    break
                # same level: stop this subsection extension here; outer loop may continue
                next_end = index
                break
        end = next_end
        # Enough material collected.
        if body_quality(start, end) >= 160 and body_has_table(start, end):
            # Keep going only if the immediate next heading is still valuation-related.
            peek = end
            while peek < len(lines) and not lines[peek].strip():
                peek += 1
            if peek < len(lines):
                peek_level = heading_level(lines[peek])
                if peek_level is not None and is_hard_stop_heading(lines[peek], peek_level, start_level):
                    break
            if body_quality(start, end) >= 260:
                break

    # Always try to append the following decision/action chapter when present.
    # Many full-research reports put price bands under 「第八步：最终决策与行动清单」.
    peek = end
    while peek < len(lines) and not lines[peek].strip():
        peek += 1
    if peek < len(lines):
        peek_level = heading_level(lines[peek])
        if peek_level is not None and is_decision_action_heading(lines[peek]):
            decision_end = len(lines)
            for index in range(peek + 1, len(lines)):
                level = heading_level(lines[index])
                if level is not None and level <= peek_level and not is_decision_action_heading(lines[index]):
                    if is_hard_stop_heading(lines[index], level, start_level) or level <= start_level:
                        decision_end = index
                        break
            end = max(end, decision_end)

    body = lines[start:end]
    # Bound payload, but allow full multi-subsection valuation chapters.
    if len(body) > 900:
        body = body[:900] + ["", "> （原文后续内容已截断，完整内容见报告）"]
    markdown = "\n".join(body).strip()
    if len(markdown) < 40:
        return None
    return {
        "heading": clean_markdown(lines[start]),
        "start_line": start + 1,
        "end_line": end,
        "markdown": markdown,
    }



def normalize_company_name(name: str) -> str:
    """Collapse team / deepseek suffix folders into the underlying company name."""
    cleaned = clean_markdown(name)
    cleaned = re.sub(r"-team-\d{8}$", "", cleaned)
    cleaned = re.sub(r"-deepseek分析$", "", cleaned)
    cleaned = cleaned.replace("-被排除", "")
    return cleaned.strip() or name


def valuation_section_quality(section: dict[str, Any] | None) -> int:
    """Score a valuation section for display priority (higher is better)."""
    if not section:
        return -1
    heading = str(section.get("heading") or "")
    markdown = str(section.get("markdown") or "")
    score = 0
    if "估值与安全边际" in heading:
        score = 100
    elif re.search(r"财务质量与估值|估值与价格纪律", heading):
        score = 90
    elif re.search(r"最终投资建议|分层操作|价格区间", heading):
        score = 70
    elif re.search(r"估值更新|估值复核|三情景|行动价格", heading):
        score = 55
    elif "估值" in heading:
        score = 30
    # Prefer sections that still contain original Markdown tables.
    if "|" in markdown and re.search(r"\|\s*:-?\s*\|", markdown):
        score += 15
    elif "|" in markdown:
        score += 8
    score += min(len(markdown) // 120, 20)
    return score


def prefer_valuation_section(
    selected: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Prefer the original ``估值与安全边际`` tables for the decision board.

    Current action / cutoff still come from the selected newest report. Valuation
    text prefers the selected report when it already has a solid chapter; only
    thin news/tracker notes backfill from a newer full-research report.
    """

    def path_bias(path: str) -> int:
        score = 0
        if re.search(r"news|thesis-tracker|checklist|MOC|README", path, re.I):
            score -= 40
        if re.search(r"0[1-4]-|巴菲特视角|芒格视角|李录视角|段永平视角", path):
            score -= 20
        if re.search(r"investment-team|研究报告|最终报告|research", path, re.I):
            score += 15
        return score

    def score_record(record: dict[str, Any]) -> tuple[int, str, dict[str, Any] | None, str]:
        path = str(record.get("report_path") or "")
        section = record.get("valuation_section")
        if not isinstance(section, dict):
            return -1, "", None, path
        score = valuation_section_quality(section) + path_bias(path)
        # Prefer longer complete chapters over short nested fragments.
        markdown = str(section.get("markdown") or "")
        score += min(len(markdown) // 200, 15)
        cutoff = str(record.get("data_cutoff") or "")
        return score, cutoff, section, path

    selected_score, _, selected_section, selected_path = score_record(selected)
    best_score = -1
    best_cutoff = ""
    best_section: dict[str, Any] | None = None
    best_source: str | None = None

    pool: list[dict[str, Any]] = [selected, *candidates]
    seen: set[str] = set()
    for record in pool:
        path = str(record.get("report_path") or "")
        if path in seen:
            continue
        seen.add(path)
        score, cutoff, section, source = score_record(record)
        if section is None:
            continue
        if score > best_score or (score == best_score and cutoff > best_cutoff):
            best_score = score
            best_cutoff = cutoff
            best_section = dict(section)
            best_source = source

    if not best_section:
        return selected_section if isinstance(selected_section, dict) else None

    # Keep selected report's own chapter when it is already a full valuation write-up.
    if isinstance(selected_section, dict) and selected_score >= 90:
        return selected_section

    # Swap only when another report is clearly better (full research vs thin note).
    if best_score >= selected_score + 15 or (selected_score < 70 and best_score >= 95):
        if best_source and best_source != selected_path:
            best_section["source_report_path"] = best_source
            best_section["source_note"] = (
                f"当前结论来自较新跟踪稿；估值原文取自更完整报告：{best_source}"
            )
        return best_section

    if isinstance(selected_section, dict):
        return selected_section
    return best_section


def normalize_scenario_label(value: str) -> str | None:
    """Map common scenario labels onto the dashboard's three-case vocabulary."""
    cleaned = clean_markdown(value)
    if not cleaned:
        return None
    if "乐观" in cleaned:
        return "乐观"
    if "悲观" in cleaned:
        return "悲观"
    if "中性" in cleaned or "基准" in cleaned:
        return "中性"
    return None


def find_tables_near_terms(
    lines: list[str],
    heading_options: tuple[tuple[str, ...], ...],
    header_matchers: tuple[tuple[str, ...], ...],
) -> list[tuple[list[str], list[list[str]]]]:
    """Collect Markdown tables near any of several report headings.

    Each header_matcher is an OR group; every group must match at least one column.
    """
    tables: list[tuple[list[str], list[list[str]]]] = []
    for heading_index, heading in enumerate(lines):
        if not any(all(term in heading for term in option) for option in heading_options):
            continue
        for index in range(heading_index + 1, min(len(lines), heading_index + 48)):
            headers = markdown_cells(lines[index])
            if not headers:
                continue
            if index + 1 >= len(lines) or not is_markdown_table_separator(lines[index + 1]):
                continue
            if not all(any(any(term in header for term in group) for header in headers) for group in header_matchers):
                continue
            rows: list[list[str]] = []
            for row_index in range(index + 1, min(len(lines), index + 24)):
                row = markdown_cells(lines[row_index])
                if row is None:
                    if rows:
                        break
                    continue
                if len(row) == len(headers):
                    rows.append(row)
            if rows:
                tables.append((headers, rows))
            break
    return tables


def first_header_index(headers: list[str], labels: tuple[str, ...]) -> int | None:
    """Return the first column whose header contains any of the label fragments."""
    for label in labels:
        index = header_index(headers, label)
        if index is not None:
            return index
    return None



def looks_like_price_band(value: str) -> bool:
    """Return True when a cell resembles an investable price band rather than a metric note."""
    text = clean_markdown(value)
    if not text or not re.search(r"\d", text):
        return False
    if re.search(r"(市值|股本|归母|净利差|不良|资本充足|同比增长|TTM|股息率|ROE|ROA|拨备|中报|现金流|短债|FCF)", text):
        return False
    # Reject calendar years posing as prices, e.g. 2025 元.
    if re.fullmatch(r"(?:低于|高于|不高于|≤|≥|<|>)?\s*20\d{2}\s*元?", text):
        return False
    # Prefer compact price cells; long conditional sentences are not price bands.
    if len(text) > 28 and not re.search(r"(元|港元|HK\$|US\$)", text):
        return False
    if len(text) > 40 and text.count("，") + text.count(",") >= 1:
        return False
    return bool(
        re.search(
            r"(元|港元|美元|HK\$|US\$|\$|PE|x|倍|以下|以上|低于|高于|不高于|不超过|≤|≥|<|>|—|–|-|~)",
            text,
            re.I,
        )
    )


def looks_like_action(value: str) -> bool:
    """Return True when a cell describes a buy/hold/sell style action."""
    return bool(
        re.search(
            r"买入|买点|建仓|加仓|持有|观望|观察|等待|回避|减仓|卖出|配置|追高|重仓|重注|分批|积累|介入|不追|降低|暂停|小仓|重点研究|轻仓|试错|验证",
            clean_markdown(value),
        )
    )


def extract_scenario_valuation(lines: list[str]) -> list[dict[str, str]]:
    """Extract a report's three-scenario target prices when explicitly tabulated."""
    tables = find_tables_near_terms(
        lines,
        heading_options=(("三情景",), ("情景估值",), ("三情景估值",)),
        header_matchers=(("情景",), ("目标股价", "目标价", "当前价值", "目标价格")),
    )
    if not tables:
        for index, line in enumerate(lines):
            headers = markdown_cells(line)
            if not headers or not any("情景" in header for header in headers):
                continue
            rows: list[list[str]] = []
            for row_index in range(index + 1, min(len(lines), index + 24)):
                row = markdown_cells(lines[row_index])
                if row is None:
                    if rows:
                        break
                    continue
                if len(row) == len(headers):
                    rows.append(row)
            if rows:
                tables.append((headers, rows))

    for headers, rows in tables:
        scenario_index = first_header_index(headers, ("情景",))
        target_price_index = first_header_index(headers, ("目标股价", "目标价", "当前价值", "目标价格"))
        if scenario_index is None:
            continue
        if target_price_index is None:
            target_price_index = len(headers) - 1
        fields = {
            "eps_growth": first_header_index(headers, ("EPS 年增速", "年增速", "EPS/股息增速", "增速")),
            "target_pe": first_header_index(headers, ("目标 PE", "目标PE", "目标倍数")),
            "target_eps": first_header_index(headers, ("3 年后 EPS", "3年后目标EPS", "3年后 EPS", "目标EPS")),
            "upside": next(
                (
                    index
                    for index, header in enumerate(headers)
                    if any(token in header for token in ("涨跌幅", "较现价", "较当前"))
                ),
                None,
            ),
        }
        scenarios: list[dict[str, str]] = []
        for row in rows:
            scenario = normalize_scenario_label(row[scenario_index])
            if not scenario:
                continue
            target = clean_markdown(row[target_price_index])
            if not target or not re.search(r"\d", target):
                continue
            if not re.search(r"(元|港元|美元|HK\$|US\$|\$)", target, re.I):
                # Allow bare numbers only when the column header is clearly a price column.
                header = headers[target_price_index]
                if not any(token in header for token in ("目标股价", "目标价", "当前价值", "目标价格")):
                    continue
            entry = {"scenario": scenario, "target_price": target}
            for key, field_index in fields.items():
                if field_index is not None and field_index < len(row):
                    entry[key] = clean_markdown(row[field_index])
            scenarios.append(entry)
        if scenarios:
            return scenarios

    # Inline prose formats: 乐观40.0元 / 中性31.6元 / 悲观21.9元
    joined = "\n".join(lines)
    inline = re.search(
        r"乐观\s*[：:]?\s*(?P<bull>[HK$US$]?\s*\d+(?:\.\d+)?)\s*元?"
        r"[^\n]{0,40}?"
        r"中性\s*[：:]?\s*(?P<base>[HK$US$]?\s*\d+(?:\.\d+)?)\s*元?"
        r"[^\n]{0,40}?"
        r"悲观\s*[：:]?\s*(?P<bear>[HK$US$]?\s*\d+(?:\.\d+)?)\s*元?",
        joined,
    )
    if inline:
        def _price(raw: str) -> str:
            raw = re.sub(r"\s+", "", raw)
            if raw.upper().startswith(("HK$", "US$")):
                return raw if raw[-1].isdigit() else raw
            return f"{raw} 元" if not raw.endswith("元") else raw

        return [
            {"scenario": "乐观", "target_price": _price(inline.group("bull"))},
            {"scenario": "中性", "target_price": _price(inline.group("base"))},
            {"scenario": "悲观", "target_price": _price(inline.group("bear"))},
        ]

    slash = re.search(
        r"(?:三情景|情景)[^\n]{0,40}?(?P<a>\d+(?:\.\d+)?)\s*/\s*(?P<b>\d+(?:\.\d+)?)\s*/\s*(?P<c>\d+(?:\.\d+)?)\s*元",
        joined,
    )
    if slash:
        return [
            {"scenario": "乐观", "target_price": f"{slash.group('a')} 元"},
            {"scenario": "中性", "target_price": f"{slash.group('b')} 元"},
            {"scenario": "悲观", "target_price": f"{slash.group('c')} 元"},
        ]
    return []


def extract_price_plan(
    lines: list[str],
    *,
    market: str | None = None,
) -> list[dict[str, str]]:
    """Extract explicit buy, hold, and caution price bands from a report table."""
    table_specs = (
        (("价格区间建议",), (("类型", "区间", "投资者"), ("区间", "价格", "建仓价格"), ("动作", "建议"))),
        (("价格区间",), (("类型", "区间", "投资者", "投资风格"), ("区间", "价格", "建仓价格"), ("动作", "建议", "研究动作"))),
        (("行动价格带",), (("区间", "价格", "当前价格"), ("动作", "建议", "行动", "预期年化"))),
        (("分层操作建议",), (("投资者", "类型"), ("建仓价格", "价格区间", "区间"), ("建议", "动作"))),
        (("分层价格区间",), (("投资风格", "类型", "风格"), ("价格区间", "区间", "价格"), ("研究动作", "建议", "动作"))),
        (("合理价格区间",), (("区间", "价格"), ("动作", "建议"))),
        (("价格区间",), (("价格区间",), ("建议", "动作"))),
    )
    tables: list[tuple[list[str], list[list[str]]]] = []
    for heading_terms, header_groups in table_specs:
        tables.extend(find_tables_near_terms(lines, (heading_terms,), header_groups))

    for index, line in enumerate(lines):
        headers = markdown_cells(line)
        if not headers:
            continue
        if index + 1 >= len(lines) or not is_markdown_table_separator(lines[index + 1]):
            # Body rows can contain words such as "价格" and "建议". Requiring
            # a real header separator prevents position limits and signal
            # numbers from being parsed as share-price bands.
            continue
        joined = " ".join(headers)
        if not any(
            token in joined
            for token in ("价格区间", "行动", "价格带", "合理价格", "买入价")
        ) and not (
            any("区间" in header or "价格" in header for header in headers)
            and any(
                any(
                    token in header
                    for token in (
                        "建议",
                        "动作",
                        "空仓",
                        "新资金",
                        "适合",
                        "逻辑",
                        "判断",
                        "估值含义",
                        "安全边际含义",
                    )
                )
                for header in headers
            )
        ) and not (
            any(token in header for header in headers for token in ("策略", "维度", "类别"))
            and any("建议" in header for header in headers)
        ):
            continue
        rows: list[list[str]] = []
        for row_index in range(index + 1, min(len(lines), index + 24)):
            row = markdown_cells(lines[row_index])
            if row is None:
                if rows:
                    break
                continue
            if len(row) == len(headers):
                rows.append(row)
        if rows:
            tables.append((headers, rows))

    for headers, rows in tables:
        header_blob = " ".join(headers)
        if "情景" in header_blob and "目标" in header_blob:
            continue
        profile_index = first_header_index(
            headers,
            (
                "投资者类型",
                "投资风格",
                "类型",
                "策略",
                "维度",
                "情景",
                "价格区间",
                "区间",
                "价格",
                "档位",
                "安全边际",
                "风格",
            ),
        )
        range_index = None
        market_price_headers = {
            "A股": ("A股价格", "A 股价格", "人民币价格"),
            "港股": ("H股价格", "H 股价格", "港股价格", "港元价格"),
            "美股": ("美股价格", "美元价格"),
        }
        if market in market_price_headers:
            range_index = first_header_index(
                headers,
                market_price_headers[market],
            )
        if range_index is None:
            range_index = first_header_index(
                headers,
                (
                    "建仓价格区间",
                    "建仓价格",
                    "买入价格",
                    "买入价",
                    "股价",
                    "价格区间",
                    "价格",
                    "区间",
                ),
            )
        action_index = first_header_index(
            headers,
            (
                "动作建议",
                "操作建议",
                "具体建议",
                "动作",
                "建议",
                "新资金动作",
                "行动",
                "适合",
                "逻辑",
                "判断",
                "估值含义",
                "安全边际含义",
            ),
        )
        empty_money_index = first_header_index(
            headers,
            ("空仓者", "空仓", "新资金", "未持有者"),
        )
        if action_index is None and empty_money_index is not None:
            # Some reports provide separate 空仓者 / 持仓者 columns. The
            # dashboard's entry-price layers should follow the empty-money
            # action rather than mix two different position states.
            action_index = empty_money_index
        rationale_index = next(
            (
                index
                for index, header in enumerate(headers)
                if any(token in header for token in ("逻辑", "隐含", "对应估值", "对应PE", "预期年化"))
            ),
            None,
        )
        if profile_index is None or action_index is None:
            continue
        if range_index is None or range_index == profile_index:
            for candidate in range(len(headers)):
                if candidate in {profile_index, action_index}:
                    continue
                if any(token in headers[candidate] for token in ("价格", "区间")):
                    range_index = candidate
                    break
        plans: list[dict[str, str]] = []
        for row in rows:
            profile = clean_markdown(row[profile_index])
            action = clean_markdown(row[action_index]) if action_index is not None and action_index < len(row) else ""
            if range_index is None:
                # Generic "策略 | 具体建议" tables sometimes put the price
                # inside the value cell. Require an explicit currency so
                # years, percentages, and position sizes are not treated as
                # share-price bands.
                price_range = next(
                    (
                        clean_markdown(cell)
                        for cell in row
                        if looks_like_price_band(cell)
                        and re.search(
                            r"元|港元|美元|HK\$|US\$|\$",
                            clean_markdown(cell),
                            re.I,
                        )
                    ),
                    "",
                )
            else:
                price_range = _price_range_with_header_unit(
                    clean_markdown(row[range_index]),
                    headers[range_index],
                    market,
                )
            if not profile and not price_range:
                continue
            if range_index is not None and range_index == profile_index:
                # First column is already the band.
                if looks_like_price_band(profile):
                    price_range = profile
                    profile = action or "价格带"
                elif looks_like_price_band(price_range):
                    profile = profile or action or "价格带"
            if not looks_like_price_band(price_range):
                continue
            semantic_action_column = bool(
                action_index is not None
                and any(
                    token in headers[action_index]
                    for token in ("判断", "估值含义", "安全边际含义")
                )
            )
            if not (
                semantic_action_column
                or looks_like_action(action)
                or looks_like_action(profile)
                or looks_like_action(price_range)
            ):
                continue
            if not looks_like_action(action) and looks_like_action(profile):
                action = profile
            # Prefer concise labels when the action column is already descriptive.
            if looks_like_action(action) and (not profile or profile == price_range or looks_like_price_band(profile)):
                profile = action
            # Prefer an explicit per-share currency token over PE, position
            # size, market-cap, or signal numbers that may appear earlier.
            explicit_suffix = re.search(
                r"((?:不高于|不低于|不超过|低于|高于|≤|≥|<|>|约)?\s*"
                r"\d+(?:\.\d+)?"
                r"(?:\s*[-—–~至到]\s*\d+(?:\.\d+)?)?\s*"
                r"(?:港元|美元|(?<![亿万千百])元)\s*(?:以下|以上|以内|附近|起)?)",
                price_range,
                re.I,
            )
            explicit_prefix = re.search(
                r"((?:不高于|不低于|不超过|低于|高于|≤|≥|<|>|约)?\s*"
                r"(?:CNY|RMB|HKD|USD|HK\$|US\$|\$)\s*"
                r"\d+(?:\.\d+)?"
                r"(?:\s*[-—–~至到]\s*\d+(?:\.\d+)?)?\s*"
                r"(?:以下|以上|以内|附近|起)?)",
                price_range,
                re.I,
            )
            compact = explicit_suffix or explicit_prefix or re.search(
                r"((?:不高于|不低于|低于|高于|≤|≥|<|>|约)?\s*"
                r"(?:(?:HK|US)?\$)?\s*\d+(?:\.\d+)?"
                r"(?:\s*[-—–~至到]\s*\d+(?:\.\d+)?)?\s*"
                r"(?:元|港元|美元)?\s*(?:以下|以上|以内|附近)?)",
                price_range,
            )
            if not (explicit_suffix or explicit_prefix) and re.search(
                r"亿元|万元|千元|百元|PE|PB|PS|倍|x\b|%",
                price_range,
                re.I,
            ):
                continue
            if compact and (
                range_index is None
                or len(price_range) > len(compact.group(1)) + 2
            ):
                price_range = clean_markdown(compact.group(1))
            entry = {
                "profile": profile or "价格带",
                "price_range": price_range,
                "action": action or profile or "见报告",
            }
            if rationale_index is not None and rationale_index < len(row):
                rationale = clean_markdown(row[rationale_index])
                if rationale and not looks_like_price_band(rationale):
                    entry["rationale"] = rationale
            plans.append(entry)
        # Keep only tables that look like multi-band action plans.
        if len(plans) >= 2 and sum(1 for item in plans if looks_like_action(item["action"]) or looks_like_action(item["profile"])) >= 2:
            return plans
    return []




def normalize_investor_stance(label: str) -> str | None:
    """Map free-form investor-type labels onto 激进型 / 稳健型 / 保守型."""
    text = clean_markdown(label or "")
    if not text:
        return None
    # Metric / contract language such as "保守口径约9亿元" is not a stance label.
    if re.search(r"口径|亿元|万千瓦|中标金额|候选报价", text) and not re.search(
        r"激进型|稳健型|保守型|进取型", text
    ):
        return None
    # Rows describing holders or pure market prices are not investor styles.
    if re.search(r"已有持仓|已持有|现有持有|当前持有|持仓者|已持仓|趋势交易|当前价", text):
        if not re.search(r"激进型|稳健型|保守型|进取型|空仓", text):
            return None
    if re.search(r"保守型|空仓[、,/\s]*保守|保守[型者]", text):
        return "保守型"
    if re.search(r"稳健型|空仓[、,/\s]*稳健|稳健[型者]", text):
        return "稳健型"
    if re.search(r"激进型|进取型|空仓[、,/\s]*激进|空仓[、,/\s]*进取|激进[型者]|VC风格|周期交易", text):
        return "激进型"
    # Short standalone labels: 保守 / 稳健 / 激进 / 空仓稳健
    if re.fullmatch(r"(?:空仓)?(?:保守|稳健|激进|进取)", text):
        token = re.search(r"保守|稳健|激进|进取", text)
        mapping = {"保守": "保守型", "稳健": "稳健型", "激进": "激进型", "进取": "激进型"}
        return mapping.get(token.group(0) if token else "")
    return None


def extract_step8_lines(lines: list[str]) -> list[str]:
    """Prefer the final decision / action checklist chapter when present."""
    starts: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        level = heading_level(line)
        if level is None:
            continue
        if re.search(
            r"最终决策与行动|最终决策|行动清单|最终投资建议|最终建议|"
            r"第八步|第8步|第 8 步|八、最终|分层操作建议|分层价格区间|"
            r"操作建议|行动价格带|价格区间建议",
            line,
        ):
            # Higher score for true step-8 style headings.
            score = 100 if re.search(r"最终决策|行动清单|第八|最终建议|最终投资", line) else 70
            starts.append((score, index))
    if not starts:
        return []
    starts.sort(key=lambda item: (-item[0], item[1]))
    start = starts[0][1]
    start_level = heading_level(lines[start]) or 2
    end = len(lines)
    for index in range(start + 1, len(lines)):
        level = heading_level(lines[index])
        if level is not None and level <= start_level and index > start + 1:
            # Keep adjacent related action/price subchapters.
            if re.search(
                r"最终|行动|操作|价格|分层|清单|买入|Checklist|空仓|持仓",
                lines[index],
            ):
                continue
            end = index
            break
    return lines[start:end]



def _price_from_cells(
    cells: list[str],
    headers: list[str] | None = None,
) -> str | None:
    """Pick the most price-like cell from a table row."""
    best: tuple[int, str] | None = None
    price_token = re.compile(
        r"(?:不高于|不低于|低于|高于|≤|≥|<|>|约)?\s*"
        r"(?:HK\$|US\$|₩)?\s*"
        r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
        r"(?:\s*[-—–~至到]\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)?\s*"
        r"(?:元|港元|美元|韩元)?",
        re.I,
    )
    for cell_index, cell in enumerate(cells):
        text = clean_markdown(cell)
        if not text or not re.search(r"\d", text):
            continue
        header = clean_markdown(
            headers[cell_index]
            if headers and cell_index < len(headers)
            else ""
        )
        explicit_currency = bool(
            re.search(r"元|港元|美元|韩元|HK\$|US\$|\$|₩", text, re.I)
        )
        price_header = bool(
            re.search(r"价格|股价|价位|买入价|价格区间", header)
        )
        if not explicit_currency and not price_header:
            continue
        if explicit_currency and re.search(
            r"亿元|亿港元|亿美元|万元|万股|铜价|金价|油价|/吨|每吨",
            text,
        ):
            continue
        if not explicit_currency and re.search(
            r"%|20\d{2}|年|季度|收入|利润|回撤|市值|PE|PB|PS|倍",
            text,
            re.I,
        ):
            continue
        # Reject revenue / contract magnitudes that are not share prices.
        if re.search(r"亿元|万千瓦|亿港元|亿美元", text) and not re.search(r"\d+(?:\.\d+)?\s*元", text):
            continue
        score = 0
        if looks_like_price_band(text):
            score += 40
        if re.search(r"(元|港元|美元|HK\$|US\$|\$|₩|韩元)", text, re.I):
            score += 20
        if re.search(r"(不高于|不低于|低于|高于|≤|≥|<|>|约|\d\s*[-—–~至到]\s*\d)", text):
            score += 10
        if re.search(r"(PE|PB|PS|市盈|市净|倍|x\b)", text, re.I) and not re.search(r"元|港元|HK\$|US\$", text, re.I):
            score -= 15
        if re.search(r"亿元|中标|报价口径", text):
            score -= 40
        score -= min(len(text) // 20, 8)
        token_matches = list(price_token.finditer(text))
        compact = next(
            (
                match
                for match in token_matches
                if re.search(
                    r"元|港元|美元|韩元|HK\$|US\$|\$|₩",
                    match.group(0),
                    re.I,
                )
            ),
            token_matches[0] if token_matches else None,
        )
        if compact:
            score += 15
            display = clean_markdown(compact.group(0))
        else:
            display = text if looks_like_price_band(text) else None
        if not display or score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, display)
    return best[1] if best else None



def _action_label_from_cells(cells: list[str], stance: str) -> str:
    """Pick an action phrase that is not merely the stance label."""
    preferred: list[tuple[int, str]] = []
    for cell in cells:
        text = clean_markdown(cell)
        if not text:
            continue
        if normalize_investor_stance(text) == stance and not looks_like_action(text):
            continue
        if looks_like_price_band(text) and len(text) < 24 and not looks_like_action(text):
            continue
        rank = 2
        if looks_like_action(text) or re.search(
            r"等待|观望|回避|跟踪|试探|试错|配置|持有|买入|建仓|减仓|卖出|观察池|不追|重仓|轻仓|小仓|考虑|研究",
            text,
        ):
            rank = 0
        elif normalize_investor_stance(text) is None and not re.search(r"亿元|中标|口径", text):
            rank = 1
        else:
            continue
        clipped = re.split(r"[；;。]", text)[0].strip()
        preferred.append((rank, clipped or text))
    if preferred:
        preferred.sort(key=lambda item: (item[0], len(item[1])))
        return preferred[0][1][:60]
    return "见报告"


def _note_from_cells(cells: list[str], used: set[str]) -> str | None:
    for cell in cells:
        text = clean_markdown(cell)
        if not text or text in used:
            continue
        if len(text) < 8:
            continue
        if looks_like_price_band(text) and len(text) < 28:
            continue
        if normalize_investor_stance(text) and len(text) < 12:
            continue
        return text[:160]
    return None


def _stances_from_table_rows(headers: list[str], rows: list[list[str]]) -> dict[str, dict[str, str]]:
    """Collect investor stances from one Markdown table."""
    collected: dict[str, dict[str, str]] = {}
    header_blob = " ".join(headers)
    if "情景" in header_blob and not re.search(
        r"投资者|投资风格|建议|动作|操作|纪律",
        header_blob,
    ):
        return collected
    looks_investorish = bool(
        re.search(r"投资者|投资风格|类型|风格|档位|价格区间|建议|动作|合理动作", header_blob)
        or any(normalize_investor_stance(cell) for row in rows for cell in row)
    )
    if not looks_investorish:
        return collected

    for row in rows:
        cells = [clean_markdown(cell) for cell in row]
        if not any(cells):
            continue
        stance = None
        stance_cell = ""
        for cell in cells:
            stance = normalize_investor_stance(cell)
            if stance:
                stance_cell = cell
                break
        if stance is None:
            # Price-first tables: action cell embeds "稳健型重点买入区".
            for cell in cells:
                maybe = normalize_investor_stance(cell)
                if maybe and looks_like_action(cell):
                    stance = maybe
                    stance_cell = cell
                    break
        if stance is None:
            continue
        price = _price_from_cells(cells, headers)
        action = _action_label_from_cells(cells, stance)
        used = {stance_cell, action}
        if price:
            used.add(price)
        note = _note_from_cells(cells, used)
        # Prefer richer later rows only if missing fields.
        previous = collected.get(stance)
        entry = {
            "stance": stance,
            "action": action,
            "price_range": price or (previous or {}).get("price_range") or "",
        }
        if note:
            entry["note"] = note
        elif previous and previous.get("note"):
            entry["note"] = previous["note"]
        if previous:
            # Keep the more action-like / longer action text.
            if looks_like_action(previous.get("action", "")) and not looks_like_action(action):
                entry["action"] = previous["action"]
            if previous.get("price_range") and not entry.get("price_range"):
                entry["price_range"] = previous["price_range"]
        collected[stance] = entry
    return collected


def _stances_from_lines(lines: list[str]) -> list[dict[str, str]]:
    """Scan Markdown tables in a line window for layered investor stances."""
    collected: dict[str, dict[str, str]] = {}
    index = 0
    while index < len(lines):
        headers = markdown_cells(lines[index])
        if headers is None:
            index += 1
            continue
        rows: list[list[str]] = []
        row_index = index + 1
        # Skip separator rows handled by markdown_cells returning None / empty.
        while row_index < min(len(lines), index + 30):
            row = markdown_cells(lines[row_index])
            if row is None:
                if rows:
                    break
                row_index += 1
                continue
            if len(row) == len(headers) or (rows and abs(len(row) - len(headers)) <= 1):
                # Normalize short/long rows lightly.
                if len(row) < len(headers):
                    row = row + [""] * (len(headers) - len(row))
                rows.append(row[: len(headers)])
            elif rows:
                break
            row_index += 1
        if rows:
            for stance, entry in _stances_from_table_rows(headers, rows).items():
                if stance not in collected or (
                    not collected[stance].get("price_range") and entry.get("price_range")
                ):
                    collected[stance] = entry
            index = row_index
            continue
        index += 1

    ordered = [collected[name] for name in ("激进型", "稳健型", "保守型") if name in collected]
    return ordered


def stances_from_price_plan(price_plan: list[dict[str, str]]) -> list[dict[str, str]]:
    """Normalize an extracted price-plan table into investor stances when possible."""
    collected: dict[str, dict[str, str]] = {}
    for item in price_plan or []:
        profile = item.get("profile") or ""
        action = item.get("action") or ""
        stance = normalize_investor_stance(profile) or normalize_investor_stance(action)
        if stance is None:
            continue
        entry = {
            "stance": stance,
            "action": action if looks_like_action(action) else (profile if looks_like_action(profile) else action or profile or "见报告"),
            "price_range": item.get("price_range") or "",
        }
        if item.get("rationale"):
            entry["note"] = item["rationale"]
        collected[stance] = entry
    return [collected[name] for name in ("激进型", "稳健型", "保守型") if name in collected]


def _price_plan_market(item: dict[str, str]) -> str | None:
    """Identify an explicitly denominated price-plan row."""
    blob = " ".join(
        str(item.get(field) or "")
        for field in ("price_range", "profile", "action")
    )
    if re.search(r"港元|HK\$|HKD", blob, re.I):
        return "港股"
    if re.search(r"美元|US\$|USD|(?<!HK)\$", blob, re.I):
        return "美股"
    if re.search(r"\d\s*元", blob):
        return "A股"
    return None


def _price_plan_matches_market(item: dict[str, str], market: str | None) -> bool:
    """Keep A/H/US price bands from leaking into another listing's row."""
    row_market = _price_plan_market(item)
    if not market or market == "未识别" or row_market is None:
        return True
    return row_market == market


def _price_plan_anchor(price_range: str) -> float | None:
    """Return the upper end of a price band for risk-tolerance ordering."""
    numbers = re.findall(r"\d+(?:\.\d+)?", clean_markdown(price_range or ""))
    if not numbers:
        return None
    values = [float(number) for number in numbers[:2]]
    return max(values)


def _compact_price_plan_action(item: dict[str, str]) -> tuple[str, str | None]:
    """Make long action-discipline cells fit the layered dashboard row."""
    original = clean_markdown(
        item.get("action") or item.get("profile") or "见报告"
    )
    original = re.sub(r"^(?:[-*>]\s*)+", "", original).strip()
    compact = re.sub(r"[（(]\s*现价[^）)]*[）)]", "", original).strip()
    if re.search(r"[：:]", compact):
        left, right = re.split(r"[：:]", compact, maxsplit=1)
        left = left.strip()
        right = right.strip()
        if looks_like_action(left) and not looks_like_price_band(left):
            compact = left
        elif looks_like_price_band(left) and looks_like_action(right):
            compact = right
    first_sentence = re.split(r"[。；;]", compact, maxsplit=1)[0].strip()
    if first_sentence:
        compact = first_sentence
    if len(compact) > 60:
        compact = compact[:59].rstrip("，, ") + "…"
    note = clean_markdown(item.get("rationale") or "")
    if not note and original != compact:
        note = original
    return compact or "见报告", note or None


def _price_plan_action_kind(action: str) -> str | None:
    """Classify one price-band action as buy, watch, or unusable."""
    text = clean_markdown(action or "")
    positive_action = re.sub(
        r"(?:不|勿|停止|暂停|暂缓|无需|无须|不建议|不宜|不急于|不必|避免)"
        r"[^，。；;]{0,5}(?:买入|建仓|加仓|配置)",
        "",
        text,
    )
    positive_action = re.sub(
        r"分批[^，。；;]{0,4}(?:减仓|卖出|退出)|"
        r"(?:减仓|卖出|退出)[^，。；;]{0,4}分批",
        "",
        positive_action,
    )
    is_buy = bool(
        re.search(
            r"买入|买点|建仓|加仓|增持|配置|小仓|轻仓|重仓(?!者)|积累|介入|"
            r"重注|分批|试探|试错|研究性|"
            r"\d+\s*/\s*\d+\s*仓|建立[^，。；;]{0,8}仓位|"
            r"(?:建立|可建)[^，。；;]{0,4}观察仓",
            positive_action,
        )
    )
    is_watch = bool(
        re.search(
            r"持有|观望|观察|等待|不追|不加仓|不新建仓|暂停|不新增|无安全边际",
            text,
        )
    )
    is_exit = bool(
        re.search(
            r"减仓|卖出|清仓|降低仓位|回避|不建议买入|不宜买入",
            text,
        )
    )
    if is_exit and not is_buy:
        return None
    if is_buy:
        return "buy"
    if is_watch:
        return "watch"
    return None


def infer_stances_from_price_plan(
    price_plan: list[dict[str, str]],
    *,
    market: str | None = None,
) -> list[dict[str, str]]:
    """Infer layered display rows from one report's unlabeled action bands.

    The fallback is intentionally conservative: it requires at least one
    buy/build-position band and at least two distinct usable price bands.
    Explicit investor-style labels remain authoritative.
    """
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(price_plan or []):
        if not isinstance(item, dict) or not _price_plan_matches_market(item, market):
            continue
        action = clean_markdown(
            item.get("action") or item.get("profile") or ""
        )
        price_range = clean_markdown(item.get("price_range") or "")
        anchor = _price_plan_anchor(price_range)
        if not action or anchor is None:
            continue
        kind = _price_plan_action_kind(action)
        if kind is None:
            continue
        candidates.append(
            {
                "index": index,
                "item": item,
                "anchor": anchor,
                "kind": kind,
            }
        )

    buy_candidates = [item for item in candidates if item["kind"] == "buy"]
    if not buy_candidates:
        return []

    # Keep one row per price boundary. Prefer a buy action over a watch action
    # when a report repeats the same boundary in adjacent rows.
    distinct: dict[float, dict[str, Any]] = {}
    for candidate in candidates:
        previous = distinct.get(candidate["anchor"])
        if previous is None or (
            previous["kind"] == "watch" and candidate["kind"] == "buy"
        ):
            distinct[candidate["anchor"]] = candidate
    candidates = list(distinct.values())
    # A prose report may repeat the current quote inside a wider actionable
    # band. Keep the band and drop the redundant point-in-time quote.
    filtered_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        item = candidate["item"]
        price_numbers = re.findall(
            r"\d+(?:\.\d+)?",
            clean_markdown(item.get("price_range") or ""),
        )
        action_text = clean_markdown(item.get("action") or "")
        nested_current = False
        if len(price_numbers) == 1 and re.search(r"当前|现价|当前位置", action_text):
            point = float(price_numbers[0])
            for other in candidates:
                if other is candidate:
                    continue
                other_numbers = re.findall(
                    r"\d+(?:\.\d+)?",
                    clean_markdown(
                        other["item"].get("price_range") or ""
                    ),
                )
                if len(other_numbers) >= 2:
                    lower, upper = sorted(
                        (float(other_numbers[0]), float(other_numbers[1]))
                    )
                    if lower <= point <= upper:
                        nested_current = True
                        break
        if not nested_current:
            filtered_candidates.append(candidate)
    candidates = filtered_candidates
    buy_candidates = sorted(
        (item for item in candidates if item["kind"] == "buy"),
        key=lambda item: (-item["anchor"], item["index"]),
    )
    watch_candidates = sorted(
        (item for item in candidates if item["kind"] == "watch"),
        key=lambda item: (item["anchor"], item["index"]),
    )

    selected: list[dict[str, Any]]
    if len(buy_candidates) >= 3:
        middle = buy_candidates[len(buy_candidates) // 2]
        selected = [buy_candidates[0], middle, buy_candidates[-1]]
    elif watch_candidates and len(buy_candidates) >= 2:
        # Closest wait/observe band, first entry band, and deepest entry band.
        selected = [watch_candidates[0], buy_candidates[0], buy_candidates[-1]]
    elif watch_candidates and buy_candidates:
        selected = [watch_candidates[0], buy_candidates[0]]
    else:
        selected = buy_candidates

    # Remove any duplicate selected rows and require real layering.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[float, int]] = set()
    for candidate in selected:
        key = (candidate["anchor"], candidate["index"])
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    if len(unique) < 2:
        return []

    stance_names = (
        ("激进型", "稳健型", "保守型")
        if len(unique) >= 3
        else ("激进型", "保守型")
    )
    stances: list[dict[str, str]] = []
    for stance, candidate in zip(stance_names, unique[:3]):
        item = candidate["item"]
        action, note = _compact_price_plan_action(item)
        price_range = _price_range_with_header_unit(
            clean_markdown(item.get("price_range") or ""),
            "",
            market,
        )
        executable_price = not bool(
            re.search(r"PE|PB|PS|倍|x\b|%", price_range, re.I)
        )
        entry = {
            "stance": stance,
            "action": action,
            "price_range": price_range,
            "source": "inferred_price_plan",
            "buy_eligible": candidate["kind"] == "buy" and executable_price,
        }
        if note:
            entry["note"] = note
        stances.append(entry)
    return stances


def _compact_valuation_band_meaning(meaning: str) -> str:
    """Prefer the decision-bearing phrase from a valuation-band explanation."""
    text = clean_markdown(meaning or "")
    if "安全边际充分" in text:
        return "安全边际充分"
    if "赔率明显占优" in text:
        return "赔率明显占优"
    if "估值合理偏低" in text:
        return "估值合理偏低，需条件验证" if re.search(r"验证|确认|等待", text) else "估值合理偏低"
    first_sentence = re.split(r"[。；;]", text, maxsplit=1)[0].strip()
    if len(first_sentence) > 60:
        return first_sentence[:59].rstrip("，, ") + "…"
    return first_sentence or "见报告"


def _price_range_with_header_unit(
    price_range: str,
    header: str,
    market: str | None,
) -> str:
    """Attach a currency unit when it exists only in a table header."""
    price = clean_markdown(price_range or "")
    header_text = clean_markdown(header or "")
    if not price or re.search(
        r"元|港元|美元|韩元|HK\$|US\$|(?<![A-Z])\$|₩|CNY|RMB|HKD|USD|KRW",
        price,
        re.I,
    ):
        return price
    if re.search(r"港元|HKD|HK\$", header_text, re.I):
        return f"{price} 港元"
    if re.search(r"美元|USD|US\$", header_text, re.I):
        return f"{price} 美元"
    if re.search(r"人民币|CNY|RMB", header_text, re.I):
        return f"{price} 元"
    # Bare numeric bands are common in older tables. The selected listing
    # market supplies the unit, but valuation multiples/percentages must stay
    # display-only rather than masquerade as share prices.
    if re.search(r"PE|PB|PS|倍|x\b|%", price, re.I):
        return price
    if not re.fullmatch(
        r"(?:不高于|不低于|不超过|低于|高于|≤|≥|<|>|约)?\s*"
        r"\d+(?:\.\d+)?"
        r"(?:\s*[-—–~至到]\s*\d+(?:\.\d+)?)?\s*"
        r"(?:以下|以上|以内|附近|起)?",
        price,
    ):
        return price
    if market == "港股":
        return f"{price} 港元"
    if market == "美股":
        return f"{price} 美元"
    if market == "A股":
        return f"{price} 元"
    return price


def infer_stances_from_valuation_bands(
    lines: list[str],
    *,
    market: str | None = None,
) -> list[dict[str, Any]]:
    """Use an explicit three-plus-band valuation table as a display-only fallback."""
    for index, line in enumerate(lines):
        headers = markdown_cells(line)
        if not headers:
            continue
        # Scenario target tables are forecasts, not investor/action layers.
        # A few reports unfortunately call valuation *zones* "情景"; retain
        # those only when the table also has an explicit action column.
        has_explicit_action_header = any(
            any(token in header for token in ("动作", "操作建议", "投资建议", "策略"))
            for header in headers
        )
        if any("指标" in header for header in headers) and not has_explicit_action_header:
            continue
        if any("情景" in header for header in headers) and not has_explicit_action_header:
            continue
        price_index = first_header_index(
            headers,
            (
                "价格区间",
                "股价区间",
                "A股价格",
                "H股价格",
                "对应价格",
                "对应股价",
                "股价范围",
                "股价",
                "价位",
                "价格",
                "区间",
            ),
        )
        meaning_index = first_header_index(
            headers,
            (
                "动作纪律",
                "投资建议",
                "操作建议",
                "策略",
                "建议",
                "估值含义",
                "安全边际含义",
                "含义",
                "估值判断",
                "判断",
                "触发条件",
            ),
        )
        if price_index is None or meaning_index is None or price_index == meaning_index:
            continue
        context_index = first_header_index(
            headers,
            ("区间定义", "区间", "档位", "情景"),
        )
        if context_index in {price_index, meaning_index}:
            context_index = None
        candidates: list[dict[str, Any]] = []
        for row_index in range(index + 1, min(len(lines), index + 18)):
            row = markdown_cells(lines[row_index])
            if row is None:
                if candidates:
                    break
                continue
            if len(row) != len(headers):
                continue
            price_range = _price_range_with_header_unit(
                row[price_index],
                headers[price_index],
                market,
            )
            meaning = clean_markdown(row[meaning_index])
            context = (
                clean_markdown(row[context_index])
                if context_index is not None
                else ""
            )
            evidence = "：".join(part for part in (context, meaning) if part)
            if not looks_like_price_band(price_range) or not meaning:
                continue
            if re.search(r"当前位置|当前价|现价", context):
                continue
            synthetic = {
                "price_range": price_range,
                "profile": context or meaning,
                "action": meaning,
            }
            if not _price_plan_matches_market(synthetic, market):
                continue
            # High-price caution rows are not part of the three useful lower
            # valuation layers.
            if re.search(r"赔率转差|明显高估|估值过高|减仓|卖出|回避", evidence):
                continue
            anchor = _price_plan_anchor(price_range)
            if anchor is None:
                continue
            candidates.append(
                {
                    "index": row_index,
                    "anchor": anchor,
                    "price_range": price_range,
                    "meaning": meaning,
                    "evidence": evidence,
                }
            )
        distinct: dict[float, dict[str, Any]] = {}
        for candidate in candidates:
            distinct.setdefault(candidate["anchor"], candidate)
        if len(distinct) < 3:
            continue
        # The three lowest valuation bands represent increasing safety margin.
        selected = sorted(
            distinct.values(),
            key=lambda item: (item["anchor"], item["index"]),
        )[:3]
        selected.reverse()
        stances: list[dict[str, Any]] = []
        for stance, candidate in zip(
            ("激进型", "稳健型", "保守型"),
            selected,
        ):
            stances.append(
                {
                    "stance": stance,
                    "action": _compact_valuation_band_meaning(candidate["meaning"]),
                    "price_range": candidate["price_range"],
                    "note": candidate["evidence"],
                    "source": "inferred_valuation_bands",
                    "buy_eligible": (
                        _price_plan_action_kind(candidate["evidence"]) == "buy"
                        and not re.search(
                            r"PE|PB|PS|倍|x\b|%",
                            candidate["price_range"],
                            re.I,
                        )
                    ),
                }
            )
        return stances
    return []


def infer_stances_from_inline_price_actions(
    lines: list[str],
    *,
    market: str | None = None,
) -> list[dict[str, Any]]:
    """Infer layers from two-plus explicit price/action phrases in report prose.

    This covers concise decision lines such as "110 元以下分批，90-100 元
    重注" without treating scenario targets or isolated valuation numbers as
    actionable bands.
    """
    price_token = re.compile(
        r"(?<![\d.])"
        r"(?:(?:不高于|不低于|低于|高于|不超过|约|≤|≥|<|>)\s*)?"
        r"(?:(?:HK|US)?\$\s*)?"
        r"\d+(?:\.\d+)?"
        r"(?:\s*[-—–~至到]\s*\d+(?:\.\d+)?)?"
        r"\s*(?:港元|美元|元)?"
        r"(?:以下|以上|以内|附近|左右|起)?"
        r"(?![\d.,%倍xX年月日亿万])",
        re.I,
    )
    candidates: list[dict[str, str]] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("|"):
            continue
        text = clean_markdown(stripped)
        if not text or len(text) > 900:
            continue
        if stripped.startswith(">") and re.search(r"巴菲特|芒格|段永平|李录", text):
            continue
        if re.search(
            r"回购|股东|员工持股|买入逻辑|买入成本|买入价没有|"
            r"愿意[^。；]{0,60}持有[^。；]{0,20}吗|能否[^。；]{0,20}加仓|"
            r"什么情况下[^。；]{0,20}买入|宁愿[^。；]{0,20}买入|"
            r"按(?:中位价|最低价|最高价)|买入[^。；]{0,15}跌到|"
            r"被套|买入价|不视为[^。；]{0,20}买入|不满足[^。；]{0,20}条件|"
            r"前提下可控|(?:^|[，。；])\s*以[^。；]{0,20}买入",
            text,
        ):
            continue
        # Split dense final-decision sentences so each price keeps its nearby
        # action rather than inheriting an unrelated action elsewhere.
        fragments = [
            fragment.strip()
            for fragment in re.split(r"[，；;。]\s*", text)
            if fragment.strip()
        ]
        if len(price_token.findall(text)) == 1:
            fragments.append(text)
        for fragment in fragments:
            if re.search(
                r"^以[^。；]{0,20}买入|愿意[^。；]{0,60}持有[^。；]{0,20}吗|"
                r"买入[^。；]{0,15}跌到|被套|买入价",
                fragment,
            ):
                continue
            kind = _price_plan_action_kind(fragment)
            if kind is None:
                continue
            match = price_token.search(fragment)
            if not match:
                continue
            price_range = clean_markdown(match.group(0))
            if not looks_like_price_band(price_range):
                continue
            if not re.search(
                r"元|港元|美元|HK\$|US\$|\$",
                price_range,
                re.I,
            ) and not re.search(
                r"股价|价格|价位|买点|买入区|建仓区",
                fragment,
            ):
                continue
            item = {
                "profile": fragment,
                "price_range": price_range,
                "action": fragment,
            }
            if not _price_plan_matches_market(item, market):
                continue
            candidates.append(item)

    stances = infer_stances_from_price_plan(candidates, market=market)
    for item in stances:
        item["source"] = "inferred_inline_price_actions"
    return stances


def _stance_prices_for_market(
    stances: list[dict[str, Any]],
    market: str | None,
) -> list[dict[str, Any]]:
    """Blank an explicit price quoted for a different listing market."""
    cleaned: list[dict[str, Any]] = []
    for stance in stances:
        item = dict(stance)
        price_range = clean_markdown(item.get("price_range") or "")
        if price_range and not _price_plan_matches_market(
            {"price_range": price_range},
            market,
        ):
            item["price_range"] = ""
        elif price_range:
            item["price_range"] = _price_range_with_header_unit(
                price_range,
                "",
                market,
            )
        cleaned.append(item)
    return cleaned


def extract_investor_stances(
    lines: list[str],
    *,
    valuation_lines: list[str] | None = None,
    price_plan: list[dict[str, str]] | None = None,
    market: str | None = None,
) -> list[dict[str, str]]:
    """Extract 激进/稳健/保守 layered advice, preferring step-8 decision tables.

    Step-7 scenario targets are intentionally not treated as investor stances.
    """
    windows: list[list[str]] = []
    step8 = extract_step8_lines(lines)
    if step8:
        windows.append(step8)
    if valuation_lines:
        windows.append(valuation_lines)
    windows.append(lines)

    best: list[dict[str, str]] = []
    for window in windows:
        stances = _stance_prices_for_market(
            _stances_from_lines(window),
            market,
        )
        if len(stances) >= 2:
            return stances
        if len(stances) > len(best):
            best = stances
        elif len(stances) == len(best) and stances and sum(1 for item in stances if item.get("price_range")) > sum(
            1 for item in best if item.get("price_range")
        ):
            best = stances

    plan_stances = _stance_prices_for_market(
        stances_from_price_plan(price_plan or []),
        market,
    )
    if len(plan_stances) >= 2:
        return plan_stances
    if len(plan_stances) > len(best):
        best = plan_stances
    if best:
        return best
    inferred_plan = infer_stances_from_price_plan(price_plan or [], market=market)
    if inferred_plan:
        return inferred_plan
    if valuation_lines:
        valuation_stances = infer_stances_from_valuation_bands(
            valuation_lines,
            market=market,
        )
        if valuation_stances:
            return valuation_stances
    valuation_stances = infer_stances_from_valuation_bands(lines, market=market)
    if valuation_stances:
        return valuation_stances
    return infer_stances_from_inline_price_actions(lines, market=market)


def classify_action_from_stances(stances: list[dict[str, str]]) -> str | None:
    """Derive a coarse filter label, preferring the 稳健型 empty-money stance."""
    if not stances:
        return None
    # Inferred display layers organize an existing price plan; they must not
    # rewrite the report's own coarse current recommendation.
    if all(str(item.get("source") or "").startswith("inferred_") for item in stances):
        return None
    by_name = {item["stance"]: item for item in stances if item.get("stance")}
    for name in ("稳健型", "激进型", "保守型"):
        item = by_name.get(name)
        if not item:
            continue
        blob = " ".join(
            part
            for part in (item.get("action"), item.get("price_range"), item.get("note"))
            if part
        )
        hit = _action_from_blob(blob)
        if hit:
            return hit
    return None


def investor_stances_summary(stances: list[dict[str, str]]) -> str | None:
    """Compact multi-angle conclusion for Obsidian tables and exports."""
    if not stances:
        return None
    parts: list[str] = []
    for item in stances:
        stance = item.get("stance") or "分层"
        action = item.get("action") or "见报告"
        price = item.get("price_range") or ""
        if price:
            parts.append(f"{stance}：{action}（{price}）")
        else:
            parts.append(f"{stance}：{action}")
    return "；".join(parts)



def preferred_buy_price(price_plan: list[dict[str, str]]) -> str | None:
    """Choose the explicit priority-buy band while retaining the full plan elsewhere."""
    ranked_keywords = (
        "优先买入",
        "稳健型分批买入",
        "稳健型",
        "小额分批买入",
        "分批买入",
        "跟踪型买入",
        "重点研究并分批建仓",
        "可分批买入",
        "分批建仓",
        "分批配置",
        "买入",
        "建仓",
        "配置",
        "积累",
    )
    for keyword in ranked_keywords:
        for item in price_plan:
            blob = f"{item.get('profile', '')} {item.get('action', '')}"
            if keyword in blob and not re.search(r"减仓|卖出|不追高|不建议追高|暂停加仓", blob):
                return item.get("price_range")
    for item in price_plan:
        blob = f"{item.get('profile', '')} {item.get('action', '')}"
        if re.search(r"买入|建仓|配置|积累", blob) and not re.search(r"减仓|卖出|不追", blob):
            return item.get("price_range")
    return None


def entity_from_path(relative_path: Path) -> tuple[str, str, str | None, str]:
    """Infer a subject, its kind, market hint, and entity directory from a path."""
    parts = relative_path.parts
    if not parts:
        return "未识别", "topic", None, ""
    # Recall pools contain company folders, but the pool root itself is not a stock.
    if parts[0] in {"港股召回池", "美股召回池", "科创板召回池", "召回池"}:
        if len(parts) >= 3:
            company = parts[1].replace("-被排除", "")
            market = "港股" if parts[0].startswith("港股") else "美股" if parts[0].startswith("美股") else None
            return company, "company", market, "/".join(parts[:2])
        return parts[0], "topic", None, parts[0]
    if parts[0] in TOPIC_DIRECTORIES:
        return parts[0], "topic", None, parts[0]
    return parts[0], "company", None, parts[0]


def is_company_equity(record: dict[str, Any]) -> bool:
    """Keep only individual-stock conclusions for the public decision board."""
    if record.get("entity_kind") != "company":
        return False
    company = str(record.get("company") or "")
    report_path = str(record.get("report_path") or "")
    if company in TOPIC_DIRECTORIES:
        return False

    non_equity_names = {
        "段永平",
        "李录",
        "瑞·达利欧",
        "银行股",
        "Temu",
        "NASDAQ-100",
        "Token中转站",
        "巴菲特镜子测试",
        "当前市场投资方向",
        "换仓决策",
        "读书与播客",
        "公众号",
        "主题文章",
        "宇视科技",
        "小红书",
        "散户乙",
        "智元机器人",
    }
    if company in non_equity_names:
        return False
    if any(marker in company for marker in INDUSTRY_NAME_MARKERS):
        return False
    if re.search(
        r"(房产研究|深度研究|宏观|组合|播客|公众号|召回池$|行业|产业|赛道|对比|筛选|指数|访谈|合集)",
        company,
    ):
        return False
    if re.search(r"(研究|分析|报告|系列|专题|地图|bottleneck)", company, re.I):
        # Team / deepseek folders are normalized before this check; leftovers stay out.
        return False
    if any(marker in report_path for marker in INDUSTRY_PATH_MARKERS) and not record.get("ticker"):
        return False

    # Listed names with a parsed ticker are always equities.
    if record.get("ticker"):
        return True

    # Private / overseas names without a ticker still count as individual companies
    # when the folder name looks like a firm rather than a theme note.
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", company))


def is_post_buy_tracking_report(record: dict[str, Any]) -> bool:
    """Return whether a report belongs exclusively to the post-buy workflow.

    Thesis and news-pulse reports are valuable library artifacts, but they must
    never supersede a pre-buy fundamental conclusion or expand the decision
    board. Their results reach the board through the explicit post-buy layer.
    """
    filename = Path(str(record.get("report_path") or "")).name
    return bool(
        re.search(
            r"(?:^|[-_])(thesis(?:[-_]?tracker)?|news(?:[-_]?pulse)?)(?:[-_.]|$)",
            filename,
            re.I,
        )
    )


def candidate_record(
    report_path: Path,
    repo_root: Path,
    registry: list[dict[str, Any]],
    overrides: dict[str, Any],
) -> dict[str, Any] | None:
    """Parse one Markdown report into a dashboard candidate, without modifying it."""
    relative = report_path.relative_to(repo_root / "reports")
    if any(part in SKIPPED_PATH_PARTS for part in relative.parts):
        return None
    # Index / scaffolding files are not research conclusions.
    if report_path.name.lower() in {"readme.md", "moc.md"}:
        return None
    text = report_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if parse_frontmatter(lines).get("type") == "technical-analysis":
        return None
    decision_contract = extract_decision_contract(lines)
    # A Checklist is a screening gate, not a replacement for a full investment
    # recommendation. Its typed contract prevents it from superseding the main report.
    if decision_contract and decision_contract["report_type"] == "company-checklist":
        return None
    valuation_section = extract_valuation_section(lines)
    section = decision_section(lines)
    if not section:
        # Some full research reports put prices under valuation / action headings
        # without a classic "最终建议" title. Still admit them when prices exist.
        has_prices = bool(
            extract_price_plan(lines)
            or extract_scenario_valuation(lines)
            or valuation_section
        )
        if not has_prices:
            return None
        section = lines[-160:] if len(lines) > 160 else lines

    entity, entity_kind, market_hint, entity_directory = entity_from_path(relative)
    entity = normalize_company_name(decision_contract["company"] if decision_contract else entity)
    ticker = (decision_contract or {}).get("ticker") or extract_ticker("\n".join(lines[:120]))
    registry_entry = registry_company(registry, entity, ticker)
    if registry_entry:
        entity = str(registry_entry["canonical_name"])
    else:
        entity = normalize_company_name(entity)
    report_relative = report_path.relative_to(repo_root).as_posix()
    report_override = overrides.get("reports", {}).get(report_relative, {})
    if not isinstance(report_override, dict):
        raise ValueError(f"Report override must be an object: {report_relative}")
    effective_ticker = report_override.get("ticker", (decision_contract or {}).get("ticker") or ticker)
    effective_market = report_override.get(
        "market", (decision_contract or {}).get("market") or market_for_ticker(effective_ticker, market_hint)
    )

    # Prefer prices from the valuation section itself; fall back to the full report.
    valuation_lines = (
        valuation_section["markdown"].splitlines()
        if valuation_section
        else lines
    )
    contract_stances = (decision_contract or {}).get("investor_stances") or []
    price_plan = report_override.get(
        "price_plan",
        contract_stances
        or extract_price_plan(valuation_lines, market=effective_market)
        or extract_price_plan(lines, market=effective_market),
    )
    scenarios = report_override.get(
        "scenario_valuation",
        extract_scenario_valuation(valuation_lines) or extract_scenario_valuation(lines),
    )
    if not isinstance(price_plan, list) or not isinstance(scenarios, list):
        raise ValueError(f"Price plan and scenario overrides must be lists: {report_relative}")
    fallback_buy_price = extract_buy_price(valuation_lines) or extract_buy_price(section)
    buy_price = report_override.get("buy_price", preferred_buy_price(price_plan) or fallback_buy_price)
    investor_stances = report_override.get(
        "investor_stances",
        contract_stances
        or extract_investor_stances(
            lines,
            valuation_lines=valuation_lines,
            price_plan=price_plan if isinstance(price_plan, list) else [],
            market=effective_market,
        ),
    )
    if not isinstance(investor_stances, list):
        raise ValueError(f"investor_stances override must be a list: {report_relative}")
    stance_action = classify_action_from_stances(investor_stances)
    coarse_action = report_override.get(
        "action", (decision_contract or {}).get("action") or stance_action or classify_action(section)
    )

    record: dict[str, Any] = {
        "company": report_override.get("company", entity),
        "entity_kind": report_override.get("entity_kind", entity_kind),
        "entity_directory": entity_directory,
        "ticker": effective_ticker,
        "market": effective_market,
        "data_cutoff": report_override.get(
            "data_cutoff", (decision_contract or {}).get("data_cutoff") or extract_data_cutoff(lines)
        ),
        "report_completed_at": report_override.get(
            "report_completed_at",
            (decision_contract or {}).get("report_completed_at") or extract_report_completed_date(lines),
        ),
        "action": coarse_action,
        "investor_stances": investor_stances,
        "conclusion_summary": report_override.get(
            "recommendation",
            (decision_contract or {}).get("summary")
            or investor_stances_summary(investor_stances)
            or extract_summary(section),
        ),
        "buy_price": buy_price,
        "price_plan": price_plan,
        "scenario_valuation": scenarios,
        "valuation_section": report_override.get("valuation_section", valuation_section),
        "recommendation": report_override.get("recommendation", extract_summary(section)),
        "title": extract_title(lines, report_path.stem),
        "report_path": report_relative,
        "report_link": report_path.relative_to(repo_root / "reports").as_posix(),
    }
    if decision_contract:
        record["decision_source"] = "看板决策契约"
        record["decision_contract"] = decision_contract
    record["price_status"] = price_status_for(record)
    record["data_status"] = "已标注" if record["data_cutoff"] else "待复核：未标注数据截止日"
    return record


def record_rank(record: dict[str, Any]) -> tuple[int, str, str, int, int, int, str]:
    """Rank candidates by cutoff, explicit completion date, then report quality.

    No filesystem timestamp or filename date participates in this ranking. A
    completion date is considered only when reports share the same explicit
    data cutoff; report content remains the final fallback for equal dates.
    """
    action_rank = {"买入": 5, "分批买入": 4, "持有": 3, "观察": 2, "减仓/卖出": 1}.get(
        record["action"], 0
    )
    price_rank = 0
    if record.get("price_plan"):
        price_rank += 2
    if record.get("scenario_valuation"):
        price_rank += 1
    if record.get("buy_price"):
        price_rank += 1
    if record.get("valuation_section"):
        price_rank += 2
    if record.get("investor_stances"):
        price_rank += min(len(record.get("investor_stances") or []), 3)
    # Prefer full research over checklist/news notes when date evidence is equal.
    kind_rank = 0
    path = str(record.get("report_path") or "")
    name = Path(path).name
    if re.search(r"investment-team|研究报告|最终报告", name, re.I):
        kind_rank += 4
    elif re.search(r"research|最终报告", path, re.I):
        kind_rank += 2
    if re.search(r"0[1-4]-|财务估值分析|巴菲特视角|芒格视角|李录视角|段永平视角", path):
        kind_rank -= 4
    if re.search(r"checklist|thesis|news|MOC", path, re.I):
        kind_rank -= 2
    return (
        1 if record["data_cutoff"] else 0,
        record["data_cutoff"] or "0000-00-00",
        record.get("report_completed_at") or "0000-00-00",
        price_rank,
        action_rank,
        kind_rank,
        record["report_path"],
    )


def report_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    """Project one report into a compact historical report-conclusion record."""
    snapshot = {
        "data_cutoff": record.get("data_cutoff"),
        "action": record.get("action"),
        "investor_stances": record.get("investor_stances") or [],
        "conclusion_summary": record.get("conclusion_summary"),
        "buy_price": record.get("buy_price"),
        "price_plan": record.get("price_plan") or [],
        "scenario_valuation": record.get("scenario_valuation") or [],
        "valuation_section": record.get("valuation_section"),
        "price_status": price_status_for(record),
        "title": record.get("title"),
        "report_path": record.get("report_path"),
        "report_link": record.get("report_link"),
    }
    if record.get("decision_contract"):
        snapshot["decision_source"] = record.get("decision_source")
        snapshot["decision_contract"] = record["decision_contract"]
    return snapshot


def usable_price_plan_rows(
    price_plan: list[dict[str, Any]] | None,
    market: str | None,
) -> list[dict[str, str]]:
    """Keep only price/action rows safe to present as an actual price reference.

    This is intentionally stricter than merely checking whether a legacy table
    contained a number.  It rejects valuation multiples and rows denominated for
    another listing, but accepts an unambiguous band whose currency is implied by
    the report's selected market.
    """
    usable: list[dict[str, str]] = []
    for row in price_plan or []:
        if not isinstance(row, dict):
            continue
        price_range = clean_markdown(str(row.get("price_range") or ""))
        action = clean_markdown(str(row.get("action") or row.get("profile") or ""))
        if (
            not price_range
            or is_contract_null(price_range)
            or not action
            or is_contract_null(action)
            or not looks_like_price_band(price_range)
            or _price_plan_anchor(price_range) is None
            or not _price_plan_matches_market(row, market)
        ):
            continue
        normalized = {
            "profile": clean_markdown(str(row.get("profile") or "")),
            "price_range": price_range,
            "action": action,
        }
        rationale = clean_markdown(str(row.get("rationale") or ""))
        if rationale:
            normalized["rationale"] = rationale
        usable.append(normalized)
    return usable


def price_status_for(
    record: dict[str, Any],
    historical_reference: dict[str, Any] | None = None,
) -> str:
    """Describe the price source without treating a historical band as current."""
    if usable_price_plan_rows(record.get("price_plan"), record.get("market")):
        return "已提取价格计划"
    if historical_reference:
        return "历史价格参照"
    if record.get("scenario_valuation"):
        return "已提取三情景"
    if record.get("buy_price"):
        return "已提取"
    return "价格未给出"


def historical_price_reference(
    selected: dict[str, Any],
    ordered: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return one transparent, market-compatible historical price reference.

    The selected report remains the sole source of current fundamental action.
    A historical price table is only attached when the selected report has no
    usable price rows, and the UI must label it as historical rather than feed it
    into live-price matching or buy/sell filters.
    """
    market = selected.get("market")
    if usable_price_plan_rows(selected.get("price_plan"), market):
        return None
    selected_path = selected.get("report_path")
    seen_paths: set[str] = set()
    for candidate in ordered:
        path = str(candidate.get("report_path") or "")
        if not path or path == selected_path or path in seen_paths:
            continue
        seen_paths.add(path)
        data_cutoff = candidate.get("data_cutoff")
        if not data_cutoff:
            # An undated price reference cannot be evaluated for freshness.
            continue
        rows = usable_price_plan_rows(candidate.get("price_plan"), market)
        if not rows:
            continue
        return {
            "source_report_path": path,
            "source_report_link": candidate.get("report_link"),
            "source_title": candidate.get("title"),
            "source_data_cutoff": data_cutoff,
            "price_plan": rows,
            "usage": "display_only",
        }
    return None


def select_decisions(records: list[dict[str, Any]], overrides: dict[str, Any]) -> list[dict[str, Any]]:
    """Select one latest stock conclusion per company and attach historical report conclusions."""
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if is_company_equity(record) and not is_post_buy_tracking_report(record):
            groups[str(record["company"])].append(record)

    selections: list[dict[str, Any]] = []
    for company, candidates in groups.items():
        ordered = sorted(candidates, key=record_rank, reverse=True)
        selected = ordered[0].copy()
        company_override = overrides.get("companies", {}).get(company, {})
        if not isinstance(company_override, dict):
            raise ValueError(f"Company override must be an object: {company}")
        selected.update(company_override)
        # Prefer original valuation tables (第七步：估值与安全边际) for display.
        preferred_section = prefer_valuation_section(selected, ordered)
        if preferred_section:
            selected["valuation_section"] = preferred_section
        historical_reference = historical_price_reference(selected, ordered)
        if historical_reference:
            selected["historical_price_reference"] = historical_reference
        selected["price_status"] = price_status_for(selected, historical_reference)
        selected["data_status"] = "已标注" if selected.get("data_cutoff") else "待复核：未标注数据截止日"
        selected["selection_basis"] = "报告数据截止日"
        # Full history remains newest-first. Historical prices never become this
        # report's price plan; a separately labelled display-only reference may
        # be attached above when the selected report itself has no usable price.
        selected["report_history"] = [report_snapshot(item) for item in ordered]
        selected["report_history_count"] = len(selected["report_history"])
        selections.append(selected)

    market_order = {"A股": 0, "港股": 1, "美股": 2, "未识别": 3}
    return sorted(selections, key=lambda item: (market_order.get(item["market"], 9), item["company"]))


def markdown_cell(value: str | None) -> str:
    """Escape a value for a compact Markdown table cell."""
    return (value or "-").replace("|", "\\|").replace("\n", " ")


def price_plan_summary(price_plan: list[dict[str, str]]) -> str | None:
    """Compress a structured price plan into a readable table cell."""
    if not price_plan:
        return None
    parts = []
    for item in price_plan:
        profile = item.get("profile") or "区间"
        price_range = item.get("price_range") or "-"
        action = item.get("action") or ""
        if action and action not in {profile, "见报告"}:
            parts.append(f"{profile} {price_range}（{action}）")
        else:
            parts.append(f"{profile} {price_range}")
    return "；".join(parts)


def scenario_summary(scenarios: list[dict[str, str]]) -> str | None:
    """Compress scenario target prices in downside-to-upside order."""
    if not scenarios:
        return None
    order = {"悲观": 0, "中性": 1, "乐观": 2}
    return "；".join(
        f"{item.get('scenario', '情景')} {item.get('target_price', '-')}"
        for item in sorted(scenarios, key=lambda item: order.get(item.get("scenario", ""), 9))
    )


def write_decision_table(path: Path, decisions: list[dict[str, Any]], generated_at: str) -> None:
    """Write the Obsidian-facing total table from generated decision records."""
    lines = [
        "---",
        'title: "投资决策总表"',
        "type: generated-index",
        f"generated_at: {generated_at}",
        "selection_rule: report-data-cutoff-only",
        "scope: individual-stocks-only",
        "---",
        "",
        "# 投资决策总表",
        "",
        "> 仅收录个股研究结论，不收录行业/主题/筛选类报告。",
        "> 当前结论只按报告明确的“数据截止日”排序，不按文件修改时间排序。",
        "> 当前结论优先读取报告末尾已校验的「看板决策契约」；旧报告则兼容解析第八步「最终决策与行动清单」等原文。粗粒度标签仅作筛选辅助。",
        "> 技术面仅用于辅助观察，不参与分层结论、综合操作筛选或买入建议。下方另附每家公司的历史研报结论。",
        "> 买入后论文追踪和异动报告仅进入持仓跟踪层，不替换基本面结论、分层价格或技术面快照。",
        "> 仅供学习与研究，不构成投资建议。",
        "",
        "| 公司 | 市场 / 代码 | 数据截止日 | 分层结论（激进/稳健/保守） | 粗粒度 | 技术面 | Checklist | 历史研报数 | 报告 |",
        "|---|---|---|---|---|---|---|---:|---|",
    ]
    for item in decisions:
        market_ticker = " / ".join(part for part in (item["market"], item.get("ticker")) if part)
        link = item["report_link"].rsplit(".", 1)[0]
        technical = item.get("technical_analysis") or {}
        technical_status = technical.get("status") if isinstance(technical, dict) else "missing"
        if technical_status == "ready":
            technical_label = f"{technical.get('state', '待复核')}（技术日 {technical.get('data_cutoff', '待复核')}）"
        elif technical_status == "review":
            technical_label = "待复核技术报告"
        else:
            technical_label = "未生成技术面报告"
        checklist = item.get("checklist") or {}
        if checklist.get("status") == "missing":
            checklist_label = "未生成"
        else:
            checklist_label = checklist.get("status", "待复核")
            if checklist.get("passed_count") is not None:
                checklist_label += f"（{checklist['passed_count']}/6）"
        layered = item.get("conclusion_summary") or investor_stances_summary(item.get("investor_stances") or []) or item.get("action")
        lines.append(
            "| {company} | {market_ticker} | {cutoff} | {layered} | {action} | {technical} | {checklist} | {history} | [[{link}|{title}]] |".format(
                company=markdown_cell(str(item["company"])),
                market_ticker=markdown_cell(market_ticker),
                cutoff=markdown_cell(item.get("data_cutoff") or "待复核"),
                layered=markdown_cell(layered),
                action=markdown_cell(item["action"]),
                technical=markdown_cell(technical_label),
                checklist=markdown_cell(checklist_label),
                history=item.get("report_history_count", len(item.get("report_history", []))),
                link=link,
                title=markdown_cell(item["title"]),
            )
        )
    review = [item for item in decisions if not item.get("data_cutoff")]
    lines.extend(["", "## 待复核", ""])
    if review:
        lines.append("以下结论缺少明确数据截止日，未被视作可比较的当前结论：")
        lines.extend(f"- [[{item['report_link'].rsplit('.', 1)[0]}|{item['company']}]]" for item in review)
    else:
        lines.append("当前入表结论均提取到了明确的数据截止日。")

    lines.extend(["", "## 技术面快照附录", ""])
    lines.append("> 技术面只辅助观察建仓节奏，不参与综合操作归类、筛选或买入建议。技术日与研报截止日相互独立。")
    for item in decisions:
        lines.extend(["", f"### {item['company']}", ""])
        technical = item.get("technical_analysis") or {}
        if technical.get("status") == "missing":
            lines.append("未生成技术面报告。")
            continue
        if technical.get("status") == "review":
            lines.append("技术报告待复核，暂不展示推断指标。")
            continue
        source_link = str(technical["report_path"]).removeprefix("reports/").rsplit(".", 1)[0]
        lines.extend(
            [
                f"技术状态：**{technical.get('state', '待复核')}**；技术日：{technical.get('data_cutoff', '待复核')}；观察区：{technical.get('observation_zone', '待复核')}",
                f"来源：[[{source_link}|技术面辅助报告]]",
                "",
                "| 短期 | 中期 | 长期 | 量能 |",
                "|---|---|---|---|",
                "| " + " | ".join(
                    markdown_cell(next((light.get('light', '待复核') for light in technical.get('lights', []) if light.get('dimension') == dimension), '待复核'))
                    for dimension in ("短期（20日）", "中期（60日）", "长期（200日）", "量能确认")
                ) + " |",
            ]
        )

    lines.extend(["", "## 买入前 Checklist 附录", ""])
    lines.append("> Checklist 是买入前筛选闸门，不覆盖基本面主报告的结论、价格计划或综合操作归类。")
    for item in decisions:
        checklist = item.get("checklist") or {}
        lines.extend(["", f"### {item['company']}", ""])
        if checklist.get("status") == "missing":
            lines.append("未生成 Checklist 报告。")
            continue
        passed = checklist.get("passed_count")
        passed_text = f"{passed}/6" if passed is not None else "待复核"
        lines.append(
            f"结论：**{checklist.get('status', '待复核')}**（{passed_text}）；"
            f"硬性否决：{checklist.get('hard_veto_label', '待复核')}；"
            f"镜子测试：{checklist.get('mirror_test', '待复核')}；"
            f"数据截止：{checklist.get('data_cutoff') or '待复核'}；"
            f"下次复核：{checklist.get('next_review_date') or '未安排'}。"
        )
        lines.extend(["", "| 关卡 | 评分 | 结果 | 核心理由 |", "|---|---|---|---|"])
        for gate in checklist.get("gates") or []:
            lines.append(
                "| {name} | {score} | {result} | {reason} |".format(
                    name=markdown_cell(gate.get("name")),
                    score=markdown_cell(gate.get("score")),
                    result=markdown_cell(gate.get("result")),
                    reason=markdown_cell(gate.get("reason")),
                )
            )
        if checklist.get("report_path"):
            link = str(checklist["report_path"]).rsplit(".", 1)[0].removeprefix("reports/")
            lines.append(f"\n来源：[[{link}|打开 Checklist 报告]]")

    lines.extend(["", "## 历史研报结论", ""])
    lines.append("> 每家公司按数据截止日从新到旧列出历次基本面研报结论。价格细节见各期报告原文；旧报告价格不会自动延续到新报告。")
    for item in decisions:
        history = item.get("report_history") or []
        if not history:
            continue
        lines.extend(
            [
                "",
                f"### {item['company']}",
                "",
                "| 数据截止日 | 结论 | 报告 |",
                "|---|---|---|",
            ]
        )
        for snap in history:
            link = str(snap.get("report_link") or "").rsplit(".", 1)[0]
            lines.append(
                "| {cutoff} | {action} | [[{link}|{title}]] |".format(
                    cutoff=markdown_cell(snap.get("data_cutoff") or "待复核"),
                    action=markdown_cell(snap.get("action")),
                    link=link,
                    title=markdown_cell(snap.get("title") or "报告"),
                )
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines)
    path.write_text("\n".join(line.rstrip() for line in content.splitlines()) + "\n", encoding="utf-8")


def write_library_moc(path: Path, reports_directory: Path, decisions: list[dict[str, Any]], generated_at: str) -> None:
    """Write a concise generated MOC for the report library."""
    selected_directories = {item["entity_directory"].split("/")[0] for item in decisions}
    all_directories = sorted(
        directory.name
        for directory in reports_directory.iterdir()
        if directory.is_dir() and not directory.name.startswith("_") and directory.name != "00-index"
    )
    company_directories = [name for name in all_directories if name in selected_directories]
    topic_directories = [name for name in all_directories if name not in selected_directories]
    lines = [
        "---",
        'title: "报告库 MOC"',
        "type: generated-index",
        f"generated_at: {generated_at}",
        "---",
        "",
        "# 报告库 MOC",
        "",
        "- [[投资决策总表]]",
        "",
        "## 有当前结论的公司",
        "",
    ]
    lines.extend(f"- [{name}](../{name}/)" for name in company_directories)
    lines.extend(["", "## 主题、比较与候选池", ""])
    lines.extend(f"- [{name}](../{name}/)" for name in topic_directories)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write stable UTF-8 JSON for the website and review workflow."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_post_buy_layer(data_directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load optional post-buy tracking and generated alert state.

    The layer is deliberately separate from report-derived decisions. Missing
    files mean that no user-confirmed positions exist; malformed files fail the
    build rather than silently attaching stale tracking state to another stock.
    """
    tracking = load_json(
        data_directory / "post_buy_tracking.json",
        {"schema_version": 1, "positions": {}},
    )
    alerts = load_json(
        data_directory / "post_buy_alerts.json",
        {"schema_version": 1, "alerts": []},
    )
    if tracking.get("schema_version") != 1 or not isinstance(tracking.get("positions"), dict):
        raise ValueError("Unsupported post-buy tracking schema")
    if alerts.get("schema_version") != 1 or not isinstance(alerts.get("alerts"), list):
        raise ValueError("Unsupported post-buy alerts schema")
    return tracking, alerts


def attach_post_buy_tracking(
    decisions: list[dict[str, Any]],
    tracking: dict[str, Any],
    alerts: dict[str, Any],
) -> dict[str, int]:
    """Attach only explicitly registered post-buy positions to board records."""
    positions = tracking.get("positions") or {}
    alerts_by_ticker: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for alert in alerts.get("alerts") or []:
        if isinstance(alert, dict) and alert.get("ticker"):
            alerts_by_ticker[str(alert["ticker"]).upper()].append(alert)

    active_count = sum(
        1
        for position in positions.values()
        if isinstance(position, dict) and (position.get("status") or "holding") == "holding"
    )
    alert_count = sum(
        1
        for alert in alerts.get("alerts") or []
        if isinstance(alert, dict) and str(alert.get("ticker") or "").upper() in positions
    )
    for decision in decisions:
        ticker = str(decision.get("ticker") or "").upper()
        registered = positions.get(ticker)
        if not isinstance(registered, dict):
            decision["post_buy_tracking"] = {"status": "not_tracked", "alerts": []}
            continue
        current_alerts = alerts_by_ticker.get(ticker, [])
        status = registered.get("status") or "holding"
        decision["post_buy_tracking"] = {
            "status": status,
            "buy_date": registered.get("buy_date"),
            "cost_basis": registered.get("cost_basis"),
            "position_weight": registered.get("position_weight"),
            "thesis_report_path": registered.get("thesis_report_path"),
            "thesis_status": registered.get("thesis_status") or "not_established",
            "health_score": registered.get("health_score"),
            "last_review_date": registered.get("last_review_date"),
            "next_review_date": registered.get("next_review_date"),
            "review_action": registered.get("review_action"),
            "metrics": registered.get("metrics") if isinstance(registered.get("metrics"), list) else [],
            "latest_event": registered.get("latest_event"),
            "alerts": current_alerts,
        }
    return {"registered_count": len(positions), "active_count": active_count, "alert_count": alert_count}


def build_dashboard(repo_root: Path = ROOT) -> dict[str, Any]:
    """Generate dashboard data and Obsidian indexes from the current report library."""
    reports_directory = repo_root / "reports"
    data_directory = repo_root / "data" / "investment-dashboard"
    site_directory = repo_root / "site"
    post_buy_tracking, post_buy_alerts = load_post_buy_layer(data_directory)
    registry = load_registry(repo_root / "data" / "report-routing" / "company_registry.json")
    overrides = load_json(
        data_directory / "overrides.json",
        {"schema_version": 1, "reports": {}, "companies": {}},
    )
    if overrides.get("schema_version") != 1:
        raise ValueError("Unsupported dashboard overrides schema")

    report_paths = sorted(reports_directory.rglob("*.md"), key=lambda item: item.as_posix().casefold())
    records = [
        record
        for report_path in report_paths
        if (record := candidate_record(report_path, repo_root, registry, overrides)) is not None
    ]
    checklist_records = [
        record
        for report_path in report_paths
        if (record := checklist_record(report_path, repo_root, registry)) is not None
    ]
    decisions = select_decisions(records, overrides)
    attach_checklists(decisions, checklist_records)
    technical_snapshots = [
        snapshot
        for report_path in report_paths
        if (snapshot := technical_snapshot(report_path, repo_root, registry)) is not None
    ]
    attach_technical_snapshots(decisions, technical_snapshots)
    post_buy_summary = attach_post_buy_tracking(decisions, post_buy_tracking, post_buy_alerts)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    catalog = {
        "schema_version": 1,
        "generated_at": generated_at,
        "record_count": len(records),
        "checklist_count": len(checklist_records),
        "records": records,
    }
    board = {
        "schema_version": 6,
        "generated_at": generated_at,
        "scope": "individual-stocks-only",
        "selection_rule": "Each stock uses the latest pre-buy fundamental report with an explicit data cutoff; filesystem modification times and filename dates are excluded. A market-compatible, dated historical price reference may be displayed only when the selected report has no usable price plan; it never becomes the current report's price plan and does not affect live-price matching, conclusions, sorting, or filters. Technical snapshots and Checklist reports are attached separately and never replace the main fundamental conclusion. Explicit post-buy thesis/news reports are attached separately. Industry/theme reports are excluded from the decision board.",
        "decision_count": len(decisions),
        "checklist_count": len(checklist_records),
        "post_buy_tracking": post_buy_summary,
        "decisions": decisions,
    }
    history_board = {
        "schema_version": 1,
        "generated_at": generated_at,
        "companies": [
            {
                "company": item["company"],
                "ticker": item.get("ticker"),
                "market": item.get("market"),
                "report_history": item.get("report_history") or [],
            }
            for item in decisions
        ],
    }
    write_json(data_directory / "reports_catalog.json", catalog)
    write_json(data_directory / "decision_board.json", board)
    write_json(data_directory / "report_history.json", history_board)
    write_json(site_directory / "data" / "reports_catalog.json", catalog)
    write_json(site_directory / "data" / "decision_board.json", board)
    write_json(site_directory / "data" / "report_history.json", history_board)
    write_json(site_directory / "data" / "post_buy_tracking.json", post_buy_tracking)
    write_json(site_directory / "data" / "post_buy_alerts.json", post_buy_alerts)
    write_decision_table(reports_directory / "00-index" / "投资决策总表.md", decisions, generated_at)
    write_library_moc(reports_directory / "00-index" / "报告库-MOC.md", reports_directory, decisions, generated_at)
    return board


def main() -> int:
    """Run the dashboard build command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    arguments = parser.parse_args()
    try:
        board = build_dashboard(arguments.repo_root.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Built {board['decision_count']} current company decisions from report data cutoffs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
