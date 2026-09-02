#!/usr/bin/env python3
"""Extract company-specific Decision Rules from canonical reports.

This is an extraction-stage tool, not part of the dashboard renderer.  It
keeps the existing structured execution-policy path as the high-confidence
fast path and adds a conservative second pass over the selected report body.
The second pass promotes only text that contains both a decision condition and
an action-changing meaning.  Plain watch lists remain monitoring metrics.
"""

from __future__ import annotations

import copy
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import decision_state
from source_hash import source_metadata_for_excerpt


SCHEMA_VERSION = decision_state.SCHEMA_VERSION

_CONDITION_RE = re.compile(
    r"如果|若|只有|除非|一旦|当.{0,24}时|前提是|条件是|连续\s*\d+|连续[一二两三四五六七八九十]+|"
    r"跌破|回调至|回落至|跌入|低于|高于|超过|达到|未达到|不低于|不高于|不超过|维持|保持|确认|出现|取得突破|"
    r"仍然|持续为负|不及预期|违约|延期|恶化|放缓|下滑|停滞|失败|失效|不再|不能"
)
_HARD_CONDITION_RE = re.compile(
    r"如果|若|只有|除非|一旦|当.{0,24}时|前提是|条件是|连续\s*\d+|连续[一二两三四五六七八九十]+|"
    r"跌破|回调至|回落至|跌入|低于|高于|超过|达到|未达到|不低于|不高于|不超过|以下|以上|满足至少|任一|任何\d+|"
    r"持续为负|不及预期|违约|延期|出现|取得突破|任何一项|任何一个|重大变化|"
    r"恶化|放缓|下滑|停滞|失败|失效|不再|不能"
)
_ACTION_RE = re.compile(
    r"买入(?!价|价格|成本|一股|评级)|建仓|加仓|增持|分批|试买|卖出|减仓|退出|放弃|停止|暂停|否决|不追|不建议|"
    r"不应在组合中|不应持有|不适合配置|不适合持有|不能买入|不值得买入|"
    r"重新评估|重新审视|重审|复核|验证|值得考虑|可以考虑|才考虑|进入买入|买入信号|"
    r"加仓信号|减仓信号|卖出信号|触发"
)
_STRONG_ACTION_RE = re.compile(
    r"买入(?!价|价格|成本|一股|评级)|建仓|加仓|增持|分批|试买|卖出|减仓|退出|放弃|停止|暂停|否决|不追|不建议|"
    r"重新评估|重新审视|重审|进入买入|买入信号|加仓信号|减仓信号|卖出信号|触发|等待"
)
_ACTION_RELATION_RE = re.compile(
    r"(?:若|如果|只有|除非|一旦|当.{0,24}时|前提是|条件是|连续\s*\d+|连续[一二两三四五六七八九十]+|"
    r"跌破|回调至|回落至|跌入|低于|高于|超过|达到|未达到|不低于|不高于|不超过|以下|以上|满足至少|任一|任何\d+|"
    r"持续为负|不及预期|违约|延期)(?:[^。！？；;]{0,48})(?:"
    r"买入(?!价|价格|成本|一股|评级)|建仓|加仓|增持|分批|试买|卖出|减仓|退出|放弃|停止|暂停|否决|不追|不建议|"
    r"不应在组合中|不应持有|不适合配置|不适合持有|不能买入|不值得买入|重新评估|"
    r"重新审视|重审|进入买入|触发)"
)
_THEN_ACTION_RE = re.compile(
    r"(?:那么|则|因此)(?:[^。！？；;]{0,40})(?:买入(?!价|价格|成本|一股|评级)|建仓|加仓|增持|卖出|减仓|退出|放弃|重审|重新评估)"
)
_DECISION_SIGNAL_RE = re.compile(
    r"增长|下降|上升|回升|下滑|改善|恶化|企稳|稳定|保持|持续|突破|跌破|回落|放松|"
    r"显现|兑现|转正|转负|恢复|回暖|反弹|见顶|止跌|放缓|不及预期|超过|低于|达到|不再|"
    r"重大变化|明确信号|风险|低利用率|低ROIC|损害|大规模扩张|发生"
)
_AMBIGUOUS_DECISION_RE = re.compile(
    r"买入窗口|安全边际|风险收益比|投资决策|分水岭|值得长期关注|择机配置|"
    r"应该买|是否值得|可以获得|估值不算便宜|当前估值"
)
_REDLINE_CONTEXT_RE = re.compile(
    r"止损(?:线|信号|条件)|回避信号|卖出信号|减仓信号|退出条件|论文失效|不建议买入|不宜重仓|"
    r"应放弃|放弃观察|停止跟踪|停止建仓|不应在组合中|不应持有|不适合配置|不适合持有|不能买入"
)
_DIRECT_RULE_RE = re.compile(
    r"合理买入价|理想买入区间|理想买入条件|买入区间|买入门槛|买入前提|触发条件|加仓条件|卖出条件|"
    r"减仓条件|止损线|停止条件|回避条件|退出信号|风险触发|不建议.*建仓|不宜重仓|不应重仓|"
    r"不应在组合中|不应持有|需要.*验证前"
)
_DECISION_HEAD_RE = re.compile(
    r"买入条件|买入触发|加仓信号|减仓信号|卖出信号|买入信号|退出条件|失效条件|"
    r"风险/失效条件|不建议买入的情形|触发加仓|触发减仓|逆袭.*条件|"
    r"合理买入价|安全边际|待建仓|触发条件|加仓条件|卖出条件|减仓条件|理想买入区间|买入门槛|"
    r"什么条件下.*买入|可以买入|考虑买入|何时.*买入|适合买入|触发买入|"
    r"可以考虑入场|何种价格.*吸引力|潜在的?入场时机|潜在的?买入时机"
)
_MONITOR_HEAD_RE = re.compile(
    r"关键监控|持续跟踪|持续追踪|跟踪清单|跟踪要点|关注指标|关键变量|观察清单|"
    r"关键跟踪指标|关键追踪指标|需要.*跟踪|需要.*追踪|验证的问题|监测指标|监控指标"
)
_REDLINE_HEAD_RE = re.compile(r"卖出|减仓|退出|失效|风险/失效条件|不建议买入的情形|回避信号|必须回避|止损|停止|放弃|否决")
_VALIDATION_HEAD_RE = re.compile(r"验证条件|复核条件|重新评估|重新审视|等待.*确认|需要验证")
_PRICE_WORD_RE = re.compile(r"股价|价格|价位|港元|港币|HK\$|人民币|元|美元|USD|回调至|跌破|PE回落|PS回落", re.I)
_OPERATING_UNIT_RE = re.compile(r"(?:元|美元|港元|人民币)\s*/\s*(?:吨|天|桶|台|件|公里|度|平方米)|每(?:吨|天|桶|台|件|公里|度|平方米)", re.I)
_ACTIONABLE_PRICE_RE = re.compile(
    r"股价\s*(?:回调|回落|跌|低于|高于|进入|接近)|价格\s*(?:回调|回落|跌|低于|高于|进入|接近)|"
    r"价位\s*(?:回调|回落|跌|低于|高于|进入|接近)|回调至|回落至|跌入|跌破|"
    r"不高于|不超过|不低于|高于|低于|进入.{0,12}(?:区间|附近)|"
    r"(?:等|等待|等到)\s*\d+(?:\.\d+)?\s*(?:元|港元|港币|HK\$|人民币|美元|USD)|附近(?:可|再|考虑)|安全边际"
)
_ADMIN_RE = re.compile(r"下一次|建议复核日|复核日期|报告落盘|数据来源|来源与数值|审计记录|交叉验证|工具核验")
_TABLE_RULE_LABEL_RE = re.compile(r"^(?:空仓者|待建仓|买入者|买入信号|加仓信号|卖出信号|减仓信号|减仓/回避信号|减仓或论文失效信号|退出条件|低估区|合理偏低|合理买入价)$")
_TABLE_ACTION_LABEL_RE = re.compile(r"^(?:观望者|短期交易者)$")
_CONTEXT_LABEL_RE = re.compile(
    r"^(?:买入条件|买入触发条件|买入信号|加仓信号|卖出信号|减仓信号|"
    r"减仓/回避信号|减仓或论文失效信号|退出条件|失效条件|回避信号|触发条件|"
    r"加仓条件|卖出条件|减仓条件)(?:\s*[（(].*)?\s*[：:]?$"
)
_METRIC_RE = re.compile(
    r"收入|营收|利润|毛利率|净利率|现金流|自由现金流|经营现金流|ROE|ROIC|PE|PS|PB|"
    r"市占|份额|产量|销量|订单|回款|应收|存货|负债|净息差|股息|分红|DAU|MAU|ARR|"
    r"油价|出货量|交付|月销|ASP|客户|付款|合作|授权|稀释|资本开支|回购|ROI|投入|利用率|"
    r"出生人口|安全区域|商业模型|时长|爆款|AI应用|市场份额|增速|估值|压缩|"
    r"市场地位|第一位置|垂直领域"
)
_SEMANTIC_VARIABLE_RE = re.compile(r"风险|系统性|商业模式|治理")
_SEMANTIC_BOUNDARY_RE = re.compile(
    r"分水岭|决定(?:是否|能否|可否).{0,24}(?:买入|建仓|加仓|重审|复核)|"
    r"(?:买入窗口|安全边际).{0,20}(?:取决于|前提|条件)"
)
_EVENT_RE = re.compile(
    r"公告|政策|监管|处罚|立案|调查|诉讼|事故|并购|收购|解禁|管理层|任命|辞职|"
    r"客户|付款|回款|违约|延期|审批|许可|控制权|竞争对手|竞品|宣布|商业化|法案|融资|分拆|IPO|大单|"
    r"限制|放松|制裁|地缘|信号|安全环保|食品安全|事件|反垄断|巨头|拒绝|补充数据|数据|疗效|差距|优于|PDUFA|结果出炉|审批结果"
)
_NUMBER_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)(?:\s*[—–-]\s*(\d+(?:\.\d+)?))?(?![\d.])")
_METADATA_RE = re.compile(r"^(?:报告日期|数据截止日|基本面建议动作|结论摘要|激进型|稳健型|保守型|买入失效条件|下次复核日期|研究置信度)")
_LABEL_ONLY_RE = re.compile(r"^(?:买入条件|买入触发条件|买入信号|加仓信号|减仓信号|卖出信号|减仓/回避信号|减仓或论文失效信号|退出条件|失效条件|风险条件|持续跟踪|持续关注|关键监控指标|关键监控|跟踪要点|关键变量|行动建议)\s*[：:]?$")
_NON_RULE_LABEL_RE = re.compile(
    r"^(?:买入条件|买入触发条件|买入信号|加仓信号|减仓信号|卖出信号|"
    r"减仓[/／](?:回避|重审|清仓|论文失效)|减仓(?:或|/|／)(?:回避|重审|清仓|论文重审|论文失效)|"
    r"卖出/减仓信号|退出条件|失效条件|回避信号|回避/清仓信号)"
    r"(?:信号)?(?:\s*[（(][^）)]*[）)])?\s*[：:]?$")

_MONITOR_SOURCE_RE = re.compile(r"^(?:证券时报|虎嗅|财联社|雪球|来源|数据来源|新闻来源|媒体报道)\s*[-—:：]")
_TABLE_HEADER_RE = re.compile(r"^(?:编号|序号|指标|事件|影响|行动建议|当前值|关注方向|说明|项目|条件|触发条件)(?:；|$)")
_RULE_LABEL_PREFIX_RE = re.compile(
    r"^(?:买入条件|买入触发条件|买入信号|加仓信号|卖出信号|减仓信号|减仓/回避信号|"
    r"减仓或论文失效信号|退出条件|失效条件|回避信号|触发条件|加仓条件|卖出条件|减仓条件|"
    r"止损线|停止条件|回避条件|退出信号|风险触发|合理买入价|理想买入区间|买入门槛)"
    r"(?:\s*[（(][^）)]*[）)])?\s*[：:]\s*"
)

_COMPOUND_JOIN_RE = re.compile(r"且|并且|同时|以及|并|或者|或|前提|之后|以后|再考虑|才考虑|；|;")
_COMPOUND_FACT_RE = re.compile(
    r"基本面|经营|季度|半年报|年报|财报|业绩|利润|现金流|OCF|FCF|ROE|ROIC|毛利率|"
    r"市占率|订单|回款|付款|到账|利用率|资本开支|负债|净债务|EBITDA|PE|PS|PB|估值|"
    r"安全边际|稀释|事故|政策|竞争|商业化|产能|收入|应收|存货|分红|股息",
    re.I,
)
_WEAK_PRICE_QUALIFIER_RE = re.compile(r"基本面未(?:坏|恶化)|基本面(?:稳定|未明显恶化)|业绩未恶化|安全边际|估值(?:太贵|过高|合理)")
_PRICE_QUALIFIER_RE = re.compile(r"PE|PS|PB|估值|安全边际", re.I)
_OPERATING_GATE_RE = re.compile(
    r"季度|半年报|年报|财报|业绩|现金流|OCF|FCF|ROE|ROIC|毛利率|市占率|订单|回款|付款|到账|"
    r"利用率|资本开支|负债|净债务|EBITDA|收入|应收|存货|分红|股息|商业化|产能|竞争",
    re.I,
)
_FACT_ALIASES = (
    ("ocf", r"经营现金流|经营性现金流|OCF"),
    ("fcf", r"自由现金流|FCF"),
    ("profit", r"归母净利润|净利润|扣非利润|扣非净利润|利润"),
    ("margin", r"毛利率|毛利"),
    ("roe", r"ROE"),
    ("roic", r"ROIC"),
    ("receivable", r"应收账款|应收"),
    ("inventory", r"存货|库存"),
    ("cash_debt", r"净债务|负债|债务|短借"),
    ("capex", r"资本开支|资本支出"),
    ("utilization", r"产能利用率|利用率"),
    ("market_share", r"市占率|市场份额|份额"),
    ("order", r"大客户订单|订单|大单"),
    ("payment", r"付款|回款|到账"),
    ("revenue", r"收入增速|营收增速|收入|营收"),
    ("dividend", r"分红率|分红|股息率|股息"),
    ("dilution", r"配股|稀释|增发"),
    ("safety", r"安全环保|安全事故|重大事故|事故"),
    ("policy", r"政策|监管|处罚|制裁|关税|碳税"),
    ("commercial", r"商业化|商业兑现|商业落地"),
    ("penetration", r"硅碳(?:负极)?渗透(?:率)?"),
    ("competitiveness", r"产品缺乏竞争力|缺乏竞争力|竞争力"),
    ("valuation", r"PE|PS|PB|估值"),
    ("price", r"股价|价格|价位|元|港元|港币|HK\$|美元|USD"),
)


def _clean_markdown(line: str) -> str:
    text = str(line or "").strip()
    if not text or text.startswith("```"):
        return ""
    if text.startswith(">"):
        text = text.lstrip("> ")
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^[-*+]\s+", "", text)
    text = re.sub(r"^\[\s*[xX ]\s*\]\s*", "", text)
    text = re.sub(r"^\d+[.)、]\s*", "", text)
    text = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩]\s*", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    if "|" in text:
        cells = [cell.strip() for cell in text.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
            return ""
        text = "；".join(cell for cell in cells if cell and not re.fullmatch(r":?-{2,}:?", cell))
    return re.sub(r"\s+", " ", text).strip(" ")


def _strip_rule_label(text: str) -> str:
    """Remove an inline signal label while retaining the condition itself."""
    result = text.strip()
    for _ in range(2):
        result = _RULE_LABEL_PREFIX_RE.sub("", result).strip()
        result = re.sub(r"^(?:[①②③④⑤⑥⑦⑧⑨⑩]|[（(]\s*\d+\s*[）)]|\d+[.)、])\s*", "", result)
        result = re.sub(r"^(?:或|或者)\s*", "", result)
    # A table cell may begin with a recommendation preamble and then state
    # the actual price/trigger after a full stop.  Keep the decision clause,
    # not the narrative lead-in (e.g. “不建议追逐……。12 元附近可建仓”).
    sentences = [part.strip() for part in re.split(r"[。！？]", result) if part.strip()]
    if len(sentences) > 1 and (_ACTIONABLE_PRICE_RE.search(sentences[-1]) or _HARD_CONDITION_RE.search(sentences[-1])):
        result = sentences[-1]
    return result.strip(" ：:，,")


def _heading(text: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+", text or ""))


def _scope_for_heading(text: str, prior: str) -> str:
    if re.search(r"不适合买入|不建议买入", text):
        return "normal"
    if re.search(r"触发性事件|触发事件", text):
        return "triggering"
    if re.search(r"最终决策|明确结论|结论摘要|行动清单", text) and not re.search(
        r"买入条件|买入信号|加仓信号|卖出信号|减仓信号|退出条件|失效条件|验证条件|安全边际|触发条件",
        text,
    ):
        # Broad conclusion sections contain reasoning and narrative.  Their
        # unlabelled sentences are not decision rules merely because they
        # mention a metric or a future scenario; labelled table rows below
        # are handled independently by the table path.
        return "normal"
    has_entry_word = bool(re.search(r"买入|加仓|行动|仓位|逆袭|合理价格区间|触发|可以买入|考虑买入|建仓|入场|吸引力", text))
    has_redline_word = bool(re.search(r"卖出|减仓|退出|失效|回避|放弃|否决", text))
    if _REDLINE_HEAD_RE.search(text) and not (has_entry_word and has_redline_word):
        return "redline"
    if _DECISION_HEAD_RE.search(text) and has_entry_word and not has_redline_word:
        return "entry"
    if _VALIDATION_HEAD_RE.search(text) and not re.search(r"买入|加仓", text):
        return "validation"
    if _MONITOR_HEAD_RE.search(text):
        return "monitoring"
    return "normal"


def _split_clauses(text: str, *, decision_context: bool = False) -> list[str]:
    """Split enumerated or independently semicolon-delimited triggers only."""
    text = re.sub(r"\s+", " ", text).strip()
    html_parts = [item.strip() for item in re.split(r"<br\s*/?>", text, flags=re.I) if item.strip()]
    if len(html_parts) > 1:
        return html_parts
    numbered = re.split(r"(?=[①②③④⑤⑥⑦⑧⑨⑩])", text)
    numbered = [item.strip(" ，,、") for item in numbered if item.strip(" ，,、")]
    if len(numbered) > 1:
        return numbered
    parenthesized = re.split(r"(?=[（(]\s*\d+\s*[）)])", text)
    parenthesized = [item.strip(" ，,、") for item in parenthesized if item.strip(" ，,、")]
    if len(parenthesized) > 1:
        # In older reports the text before “(1)” is usually an introduction,
        # e.g. “等待两个时间窗口：”, rather than a separate trigger.
        if parenthesized[0].rstrip().endswith((":", "：")) and not _HARD_CONDITION_RE.search(parenthesized[0]):
            parenthesized = parenthesized[1:]
        return parenthesized
    if not decision_context:
        return [text]
    semicolon = [item.strip(" ，,、") for item in re.split(r"[；;]", text) if item.strip(" ，,、")]
    if len(semicolon) > 1 and all(
        _CONDITION_RE.search(item)
        or _METRIC_RE.search(item)
        or _EVENT_RE.search(item)
        or _PRICE_WORD_RE.search(item)
        or _NUMBER_RE.search(item)
        for item in semicolon
    ):
        return semicolon
    alternatives = [item.strip(" ，,、") for item in re.split(r"\s*(?:或|或者)\s*", text) if item.strip(" ，,、")]
    if len(alternatives) == 2:
        comparison_join = bool(
            re.search(r"(?:接近|约|达到|不低于|不高于|低于|高于)\s*$", alternatives[0])
            and re.match(r"^(?:超过|达到|不低于|不高于|低于|高于)", alternatives[1])
        )
        left_price = bool(_PRICE_WORD_RE.search(alternatives[0]))
        right_price = bool(_PRICE_WORD_RE.search(alternatives[1]))
        left_variable = bool(_METRIC_RE.search(alternatives[0]) or _EVENT_RE.search(alternatives[0]))
        right_variable = bool(_METRIC_RE.search(alternatives[1]) or _EVENT_RE.search(alternatives[1]))
        distinct_price_alternatives = left_price and right_price and all(_NUMBER_RE.search(item) for item in alternatives)
        if not comparison_join and (
            distinct_price_alternatives
            or (left_price != right_price and (left_variable or left_price) and right_variable)
            or (
                left_variable
                and right_variable
                and (_EVENT_RE.search(alternatives[0]) or _EVENT_RE.search(alternatives[1]))
            )
            or all(_HARD_CONDITION_RE.search(item) for item in alternatives)
        ):
            return alternatives
    # A full-stop split is limited to a line that clearly contains multiple
    # action clauses, such as a buy condition followed by an alternate wait.
    sentences = [item.strip() for item in re.split(r"[。]", text) if item.strip()]
    if len(sentences) > 1 and _ACTION_RELATION_RE.search(sentences[0]) and not any(
        _ACTION_RELATION_RE.search(item) or _HARD_CONDITION_RE.search(item) for item in sentences[1:]
    ):
        return [sentences[0]]
    if len(sentences) > 1 and (
        sum(bool(_ACTION_RE.search(item) or _HARD_CONDITION_RE.search(item) or _NUMBER_RE.search(item)) for item in sentences) >= 2
    ):
        return sentences
    return [text]


def _is_monitoring_line(text: str, scope: str) -> bool:
    return scope == "monitoring" and not (_ACTION_RE.search(text) and _CONDITION_RE.search(text))


def _has_explicit_decision(text: str, scope: str, *, specific_context: bool = False) -> bool:
    if _METADATA_RE.search(text) or _LABEL_ONLY_RE.search(text) or _ADMIN_RE.search(text):
        return False
    if re.search(r"[？?]", text) and not re.search(r"需要|应当|应该|即|则|意味着|触发|重审|重新评估|重新审视", text):
        # Rhetorical mirror tests and investor questions are evidence for
        # review, not executable Decision Rules by themselves.
        return False
    condition = bool(_HARD_CONDITION_RE.search(text))
    action = bool(_ACTION_RE.search(text))
    variable = bool(_METRIC_RE.search(text) or _EVENT_RE.search(text) or _PRICE_WORD_RE.search(text) or _SEMANTIC_VARIABLE_RE.search(text))
    direct_label = bool(_DIRECT_RULE_RE.search(text))
    if scope == "normal" and _SEMANTIC_BOUNDARY_RE.search(text) and not re.search(
        r"(?:那么|则|因此|才|即)(?:[^。！？；;]{0,40})(?:买入(?!价|价格|成本|一股|评级)|建仓|加仓|增持|卖出|减仓|退出|放弃|重审|重新评估)",
        text,
    ):
        # “分水岭/判断买入还是等待” is meaningful evidence, but does not
        # state which action follows the boundary.  Keep it in the review
        # queue instead of turning a decision question into a Rule.
        return False
    if scope in {"entry", "validation", "redline", "triggering"} and specific_context:
        # A decision section provides the default action, but a bare heading,
        # score row, or descriptive sentence is still not a Rule.  It needs a
        # threshold/temporal/event condition or an explicit action-changing
        # phrase attached to a business variable.
        return (condition and variable) or (action and variable) or (_DECISION_SIGNAL_RE.search(text) and variable)
    return (
        condition
        and bool(_ACTION_RELATION_RE.search(text) or _THEN_ACTION_RE.search(text))
        and variable
    ) or (direct_label and variable)


def _positive_redline(text: str) -> bool:
    if re.search(r"(?:不是|并非|不应|无需)[^。！？；;]{0,16}(?:卖出信号|止损|回避)", text):
        return False
    return bool(_REDLINE_CONTEXT_RE.search(text))


def _rule_scope(text: str, context: str) -> str:
    if context == "triggering":
        # A triggering-event table contains its own action column.  Infer the
        # user-facing scope from the complete row instead of making every
        # event an Entry or every event a Redline.
        context = "normal"
    if context == "redline":
        return "redline"
    if context == "validation":
        return "validation"
    if context == "entry":
        # A line under an entry/add-position signal can still be a separate
        # validation gate only when the report explicitly says that the
        # thesis must be re-evaluated.  “确认/验证” inside an entry list is
        # still an Entry condition supplied by that section.
        if re.search(r"根据结果决策|重新估值", text) or (
            re.search(r"半年报|中报|年报|财报", text)
            and re.search(r"验证|确认|显示|改善|不低于|不低于旧体系", text)
            and not re.search(r"股价|价格|买入|建仓|加仓|分批", text)
        ) or (
            re.search(r"等待|等到|等候", text)
            and re.search(r"验证|确认|结果|付款|回款", text)
            and not _ACTIONABLE_PRICE_RE.search(text)
        ):
            return "validation"
        return "entry"
    if _positive_redline(text) or (
        re.search(r"卖出|减仓|退出|放弃|失效", text) and _ACTION_RELATION_RE.search(text)
    ):
        return "redline"
    if re.search(r"买入|建仓|加仓|增持|分批|试买|入场", text):
        return "entry"
    return "validation"


def _rule_type(text: str) -> str:
    # PE/PS/PB are valuation metrics, not price rules, even when a report
    # describes a valuation band.
    # Operating-unit prices such as “220 元/吨” are metrics, not stock
    # prices.  Keep the guard here so both type inference and price-field
    # parsing share the same boundary.
    if (_OPERATING_UNIT_RE.search(text) or re.search(r"单位生产成本|成本持续", text)) and not re.search(
        r"股价|股票价格|股价价格|价格进入|价位进入|回调至|回落至|跌入|跌破", text, re.I
    ):
        return "METRIC"
    price_words = re.search(r"股价|价格|价位|港元|港币|HK\$|人民币|元|美元|USD", text, re.I)
    bare_price_condition = re.match(r"\s*(?:若|如果|低于|不高于|不超过)?\s*\d+(?:\.\d+)?(?:\s*[—–-]\s*\d+(?:\.\d+)?)?\s*(?:元|港元|港币|HK\$|人民币|美元|USD)", text, re.I)
    price_text = bool(price_words and (_ACTIONABLE_PRICE_RE.search(text) or bare_price_condition))
    if price_text and _NUMBER_RE.search(text):
        return "PRICE_RANGE" if re.search(r"\d+(?:\.\d+)?\s*[—–-]\s*\d+", text) else "PRICE"
    if _EVENT_RE.search(text) and not _METRIC_RE.search(text):
        return "EVENT"
    return "METRIC"


def _price_fields(text: str, market: str | None) -> tuple[float | None, float | None, str | None]:
    if _rule_type(text) not in {"PRICE", "PRICE_RANGE"}:
        return None, None, None
    matches = list(_NUMBER_RE.finditer(text))
    if not matches:
        return None, None, None
    price_starts = [match.end() for match in _ACTIONABLE_PRICE_RE.finditer(text)]
    selected = next(
        (match for match in matches if any(0 <= match.start() - start <= 32 for start in price_starts)),
        matches[0],
    )
    first, second = selected.groups()
    low = float(first)
    high = float(second) if second else None
    if re.search(r"低于|以下|不高于|跌破", text):
        high = low
        low = None
    elif re.search(r"高于|以上|不低于|站上", text):
        high = None
    currency = "HKD" if re.search(r"港元|港币|HK\$", text, re.I) or market == "港股" else "USD" if re.search(r"美元|USD|\$", text, re.I) else "CNY"
    return low, high, currency


def _action(scope: str) -> str:
    if scope == "entry":
        return "review_decision"
    if scope == "redline":
        return "drop_or_recheck"
    return "run_drift"


def _source_excerpt(lines: list[str], start: int, end: int) -> dict[str, Any]:
    return {
        "line_start": start,
        "line_end": end,
        "text": " ".join(_clean_markdown(line) for line in lines[start - 1 : end] if _clean_markdown(line)),
    }


def _monitor_metric(text: str) -> str | None:
    if "；" in text:
        first = text.split("；", 1)[0].strip()
    else:
        first = text
    first = re.sub(r"^(指标|跟踪指标|关注指标|关键变量|关注|跟踪|观察|监测)\s*[:：]?\s*", "", first)
    first = re.sub(r"\s*(当前值|关注方向|频率|意义)\s*[:：].*$", "", first)
    first = first.strip(" ：:，,。")
    if not first or first in {"指标", "看什么", "结论", "来源", "风险"} or _MONITOR_SOURCE_RE.search(first):
        return None
    return first[:120]


def _plain_context_scope(text: str) -> str | None:
    """Return the action supplied by a non-heading signal label, if any."""
    if _CONTEXT_LABEL_RE.fullmatch(text):
        return _scope_for_heading(text, "normal")
    if (
        text.rstrip().endswith((":", "："))
        and re.search(r"(?:持续|需要持续|重点|关键).*(?:跟踪|追踪|监控).*(?:指标|变量|事项)", text)
    ):
        return "monitoring"
    if re.search(r"什么条件下.*重新审视|什么条件下.*重新评估", text):
        return "validation"
    if re.search(r"什么条件下.*买入|何种价格.*吸引力|适合买入|可以考虑入场|潜在的?入场时机|潜在的?买入时机", text):
        return "entry"
    if re.search(r"必须回避|不适合买入|潜在的?放弃信号", text):
        return "redline"
    # Older reports often introduce a list with a sentence rather than a
    # heading, e.g. “以下条件满足2-3个时，可以考虑建仓：”.  That sentence is
    # context, not itself a Rule.
    if (
        text.rstrip().endswith((":", "："))
        and re.search(r"条件|信号|前提", text)
        and re.search(r"买入|建仓|加仓|介入|行动", text)
    ):
        inferred = _scope_for_heading(text, "normal")
        return inferred if inferred != "normal" else "redline" if re.search(r"卖出|减仓|退出|失效|止损", text) else "entry"
    return None


def _semantic_candidates(lines: list[str], market: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rules: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    review_candidates: list[dict[str, Any]] = []
    context = "normal"
    context_heading = "主报告正文"
    for line_no, raw in enumerate(lines, 1):
        raw = raw.rstrip()
        if not raw or raw.startswith("```"):
            continue
        cleaned = _clean_markdown(raw)
        if not cleaned:
            continue
        if _heading(raw):
            context = _scope_for_heading(raw, context)
            context_heading = cleaned
            continue
        if _METADATA_RE.search(cleaned) or "免责声明" in cleaned or _ADMIN_RE.search(cleaned):
            continue
        is_table_row = raw.lstrip().startswith("|")
        line_context = context
        specific_context = bool(
            _DECISION_HEAD_RE.search(context_heading)
            or _VALIDATION_HEAD_RE.search(context_heading)
            or _REDLINE_HEAD_RE.search(context_heading)
        )
        decision_evidence = cleaned
        if is_table_row:
            if context == "monitoring":
                cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
                monitoring_evidence = _clean_markdown("；".join(cells))
                if (
                    len(cells) >= 2
                    and re.search(r"信号|触发|警告|阈值|分水岭|重大负面", monitoring_evidence)
                    and (_HARD_CONDITION_RE.search(monitoring_evidence) or _NUMBER_RE.search(monitoring_evidence))
                ):
                    review_candidates.append({
                        "text": monitoring_evidence,
                        "line": line_no,
                        "section": context_heading,
                        "reason": "monitoring table contains a threshold or signal but its next action is not explicit",
                    })
                metric = _monitor_metric(cleaned)
                if metric and (_METRIC_RE.search(metric) or _EVENT_RE.search(metric)):
                    metrics.append({"metric": metric, "source_excerpt": _source_excerpt(lines, line_no, line_no), "section": context_heading})
                continue
            cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
            label = re.sub(r"[*_]", "", cells[0]).strip() if cells else ""
            if context == "triggering" and _TABLE_HEADER_RE.search(_clean_markdown("；".join(cells))):
                continue
            labelled_rule = bool(_TABLE_RULE_LABEL_RE.fullmatch(label))
            labelled_action = bool(_TABLE_ACTION_LABEL_RE.fullmatch(label))
            if not labelled_rule and not labelled_action and context not in {"entry", "validation", "redline", "triggering"}:
                continue
            if re.search(r"卖出|减仓|回避|退出|失效|止损", label):
                line_context = "redline"
            elif context == "triggering":
                line_context = "triggering"
            elif context == "validation":
                line_context = "validation"
            elif labelled_action:
                line_context = "entry"
            elif not labelled_rule:
                line_context = "entry" if context == "entry" else "normal"
            else:
                line_context = "entry"
            specific_context = True
            # The label supplies the section meaning; the remaining cells
            # contain the actual condition/action text.
            body_cells = cells if context == "triggering" else cells[1:] if labelled_rule or labelled_action or len(cells) > 1 else cells
            decision_evidence = _clean_markdown("；".join(body_cells))
            # Trigger-event tables commonly have “event | impact | action”.
            # The impact/action columns justify extraction, but only the event
            # itself should become the persisted Rule condition.
            cleaned = _clean_markdown(body_cells[0] if context == "triggering" else "；".join(body_cells))
            if not cleaned:
                continue
        else:
            plain_scope = _plain_context_scope(cleaned)
            if _LABEL_ONLY_RE.fullmatch(cleaned) or plain_scope:
                context = plain_scope or _scope_for_heading(cleaned, context)
                context_heading = cleaned
                continue
            # A short prose label such as “更好的替代选择：” ends the
            # preceding decision block.  Without this reset, the following
            # ordinary recommendation bullets would inherit Entry/Validation
            # semantics from the previous section.
            if (
                cleaned.rstrip().endswith((":", "："))
                and len(cleaned) <= 60
                and not _HARD_CONDITION_RE.search(cleaned)
                and not _NUMBER_RE.search(cleaned)
                and not _has_explicit_decision(cleaned, context)
            ):
                context = "normal"
                context_heading = cleaned
                continue
        if _is_monitoring_line(cleaned, context):
            metric = _monitor_metric(cleaned)
            if metric and (_METRIC_RE.search(metric) or _EVENT_RE.search(metric)):
                metrics.append({"metric": metric, "source_excerpt": _source_excerpt(lines, line_no, line_no), "section": context_heading})
            continue
        if line_context != "redline" and _positive_redline(cleaned):
            line_context = "redline"
        if line_context == "triggering":
            specific_context = True
        if not _has_explicit_decision(decision_evidence, line_context, specific_context=specific_context):
            if (
                (_HARD_CONDITION_RE.search(decision_evidence) or _NUMBER_RE.search(decision_evidence))
                and (_DIRECT_RULE_RE.search(decision_evidence) or _ACTION_RELATION_RE.search(decision_evidence))
            ) or (
                re.search(r"(?:等待|等候|等到).{0,16}(?:价格|价位|估值|催化剂|信号|确认)", decision_evidence)
                and bool(_METRIC_RE.search(decision_evidence) or _EVENT_RE.search(decision_evidence) or _PRICE_WORD_RE.search(decision_evidence))
            ) or (
                specific_context
                and re.search(r"[？?]", decision_evidence)
                and bool(_METRIC_RE.search(decision_evidence) or _EVENT_RE.search(decision_evidence) or _PRICE_WORD_RE.search(decision_evidence))
            ):
                review_candidates.append({"text": cleaned, "line": line_no, "section": context_heading, "reason": "decision meaning is present but action mapping is ambiguous"})
            elif (
                line_context == "normal"
                and _SEMANTIC_BOUNDARY_RE.search(decision_evidence)
                and bool(_METRIC_RE.search(decision_evidence) or _EVENT_RE.search(decision_evidence) or _PRICE_WORD_RE.search(decision_evidence))
            ):
                review_candidates.append({
                    "text": cleaned,
                    "line": line_no,
                    "section": context_heading,
                    "reason": "decision boundary is present but its action mapping is not explicit enough for automation",
                })
            elif (
                line_context == "normal"
                and _AMBIGUOUS_DECISION_RE.search(decision_evidence)
                and (_HARD_CONDITION_RE.search(decision_evidence) or _NUMBER_RE.search(decision_evidence))
                and bool(_METRIC_RE.search(decision_evidence) or _EVENT_RE.search(decision_evidence) or _PRICE_WORD_RE.search(decision_evidence))
            ):
                review_candidates.append({
                    "text": cleaned,
                    "line": line_no,
                    "section": context_heading,
                    "reason": "investment implication is stated but the condition-to-action mapping is ambiguous",
                })
            continue
        clauses = _split_clauses(
            cleaned,
            decision_context=line_context in {"entry", "validation", "redline", "triggering"}
            or bool(_DIRECT_RULE_RE.search(cleaned))
            or bool(_ACTION_RELATION_RE.search(cleaned))
            or bool(_THEN_ACTION_RE.search(cleaned)),
        )
        for clause in clauses:
            clause = _strip_rule_label(clause)
            if (
                line_context == "normal"
                and _SEMANTIC_BOUNDARY_RE.search(clause)
                and not re.search(
                    r"(?:那么|则|因此|才|即)(?:[^。！？；;]{0,40})(?:买入(?!价|价格|成本|一股|评级)|建仓|加仓|增持|卖出|减仓|退出|放弃|重审|重新评估)",
                    clause,
                )
            ):
                review_candidates.append({
                    "text": clause,
                    "line": line_no,
                    "section": context_heading,
                    "reason": "decision boundary is present but its action mapping is not explicit enough for automation",
                })
                continue
            scope = _rule_scope(decision_evidence if line_context == "triggering" else clause, line_context)
            has_condition = bool(_HARD_CONDITION_RE.search(clause))
            has_variable = bool(
                _METRIC_RE.search(clause)
                or _EVENT_RE.search(clause)
                or _PRICE_WORD_RE.search(clause)
                or _SEMANTIC_VARIABLE_RE.search(clause)
            )
            if not (has_condition or (specific_context and line_context in {"entry", "validation", "redline", "triggering"} and has_variable)):
                if (
                    line_context == "normal"
                    and _SEMANTIC_BOUNDARY_RE.search(clause)
                    and has_variable
                ):
                    review_candidates.append({
                        "text": clause,
                        "line": line_no,
                        "section": context_heading,
                        "reason": "decision boundary is present but its action mapping is not explicit enough for automation",
                    })
                continue
            if not specific_context and not (
                _ACTION_RELATION_RE.search(clause)
                or _THEN_ACTION_RE.search(clause)
                or _DIRECT_RULE_RE.search(clause)
            ):
                if (
                    line_context == "normal"
                    and _SEMANTIC_BOUNDARY_RE.search(clause)
                    and has_variable
                ):
                    review_candidates.append({
                        "text": clause,
                        "line": line_no,
                        "section": context_heading,
                        "reason": "decision boundary is present but its action mapping is not explicit enough for automation",
                    })
                continue
            # In an explicitly labelled condition/signal block, the block
            # itself supplies the action meaning, so a metric-bearing bullet
            # such as "毛利率企稳" is still a Rule. Outside such a block a
            # plain metric must carry its own condition and action language.
            if line_context not in {"entry", "validation", "redline"} and not (
                _HARD_CONDITION_RE.search(clause) or _ACTION_RE.search(clause) or _EVENT_RE.search(clause)
            ):
                continue
            rule_type = _rule_type(clause)
            low, high, currency = _price_fields(clause, market)
            rules.append({
                "text": clause,
                "scope": scope,
                "type": rule_type,
                "min": low,
                "max": high,
                "currency": currency,
                "line_start": line_no,
                "line_end": line_no,
                "section": context_heading,
            })
    return rules, metrics, review_candidates


def _find_structured_excerpt(lines: list[str], condition: str) -> dict[str, Any] | None:
    tokens = [token for token in re.split(r"[，,；;。\s]+", condition) if len(token) >= 3]
    best_score = 0
    best_line: int | None = None
    for line_no, raw in enumerate(lines, 1):
        cleaned = _clean_markdown(raw)
        score = sum(token in cleaned for token in tokens) if cleaned else 0
        if score > best_score:
            best_score = score
            best_line = line_no
        if cleaned and (condition in cleaned or score >= max(1, min(3, len(tokens)))):
            return _source_excerpt(lines, line_no, line_no)
    return _source_excerpt(lines, best_line, best_line) if best_line is not None and best_score else None


def _structured_rules(decision: dict[str, Any], lines: list[str]) -> list[dict[str, Any]]:
    result = []
    for rule in decision_state._rules_for_decision(decision):
        item = copy.deepcopy(rule)
        if item.get("source") == "event_condition" and re.search(r"验证|确认|达到|满足|改善|等待|中报|半年报|年报|财报", item.get("condition", "")):
            item["rule_scope"] = "validation"
            item["action"] = "run_drift"
        item["extraction_stage"] = "structured"
        item["extraction_method"] = "structured_execution_policy"
        item["source_excerpt"] = _find_structured_excerpt(lines, item.get("condition", ""))
        result.append(item)
    return result


def _split_redline_list(text: str, *, include_or: bool = True) -> list[str]:
    """Split top-level redline lists, preserving comparator “A or B” wording."""
    protected = re.sub(
        r"(接近|低于|高于|不低于|不高于|达到|约|维持|保持)\s*或\s*(超过|达到|低于|高于|不低于|不高于)",
        r"\1§OR§\2",
        decision_state.compact(text),
    )
    separator = r"[；;、]"
    if include_or:
        separator = r"[；;、]|或者|或"
    return [part.replace("§OR§", "或").strip(" ，,、；;") for part in re.split(separator, protected) if part.strip(" ，,、；;")]


def _split_structured_redline_compounds(decision: dict[str, Any], structured: list[dict[str, Any]], lines: list[str]) -> list[dict[str, Any]]:
    """Separate independently triggerable redlines from a compound block.

    This remains intentionally narrow: only an explicitly redline-scoped item
    separated by list punctuation is split.  ``且/并且/同时`` conjunctions
    stay intact because they may be a genuine ALL_OF-style gate.
    """
    ticker = decision_state.compact(decision.get("ticker")).upper()
    result: list[dict[str, Any]] = []
    for item in structured:
        condition = decision_state.compact(item.get("condition"))
        if item.get("rule_scope") != "redline":
            result.append(item)
            continue
        if re.search(r"且|并且|同时", condition):
            result.append(item)
            continue
        parts = _split_redline_list(condition)
        if len(parts) < 2 or not all(
            len(part) >= 3 and not re.fullmatch(r"(?:并且|同时|以及|此外|其中)", part)
            for part in parts
        ):
            result.append(item)
            continue
        for index, part in enumerate(parts, 1):
            part = _strip_rule_label(part)
            if not part:
                continue
            clone = copy.deepcopy(item)
            clone["condition"] = part
            clone["rule_scope"] = "redline"
            clone["action"] = "drop_or_recheck"
            clone["type"] = _rule_type(part)
            low, high, currency = _price_fields(part, decision.get("market"))
            clone["operator"] = "between" if low is not None and high is not None else "lte" if high is not None else "gte" if low is not None else None
            clone["min"] = low
            clone["max"] = high
            clone["currency"] = currency
            clone["rule_id"] = decision_state._rule_id(
                ticker,
                clone["type"],
                part,
                f"structured_execution_policy:{item.get('source')}:{index}",
            )
            clone["source_excerpt"] = _find_structured_excerpt(lines, part)
            result.append(clone)
    return result


def _drop_compound_structured_rules(structured: list[dict[str, Any]], semantic: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer independently extracted clauses over a duplicated compound guard."""

    def clause_matches(part: str, candidate: dict[str, Any]) -> bool:
        candidate_text = decision_state.compact(candidate.get("condition"))
        if not candidate_text:
            return False
        if _same_rule({"condition": part}, candidate):
            return True
        terms = (
            "毛利率", "净债务", "EBITDA", "自由现金流", "现金流", "ROE", "ROIC", "负债",
            "资本开支", "安全环保", "事故", "订单", "回款", "应收", "存货", "分红", "市占率",
            "市占", "收入", "营收", "净利率", "利润", "客户", "制裁", "配股", "稀释", "付款",
            "延期", "违约", "商业化", "产能", "利用率", "估值", "PE", "PS", "PB", "油价",
        )
        shared_terms = [term for term in terms if term in part and term in candidate_text]
        part_numbers = set(re.findall(r"\d+(?:\.\d+)?", part))
        candidate_numbers = set(re.findall(r"\d+(?:\.\d+)?", candidate_text))
        if shared_terms and part_numbers & candidate_numbers:
            return True
        if part_numbers & candidate_numbers and (_PRICE_WORD_RE.search(part) or _PRICE_WORD_RE.search(candidate_text)):
            return True
        # Event/redline clauses frequently have no numeric threshold.  A
        # distinctive business/event term is enough when the structured and
        # semantic texts clearly refer to the same trigger.
        event_terms = {"安全环保", "事故", "制裁", "配股", "稀释", "付款", "延期", "违约", "商业化"}
        return bool(event_terms.intersection(shared_terms))

    kept: list[dict[str, Any]] = []
    for item in structured:
        if item.get("source") not in {"guard_condition", "trigger_condition", "event_condition", "invalidation_triggers"}:
            kept.append(item)
            continue
        parts = _split_clauses(decision_state.compact(item.get("condition")), decision_context=True)
        if len(parts) < 2:
            kept.append(item)
            continue
        matching = sum(1 for part in parts if any(clause_matches(part, candidate) for candidate in semantic))
        if matching < 2:
            kept.append(item)
    return kept


def _dedupe_monitoring_metrics(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for metric in metrics:
        text = decision_state.compact(metric.get("metric"))
        key = re.sub(r"\s+", "", text).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(metric)
    return result


def _semantic_rule(decision: dict[str, Any], candidate: dict[str, Any], lines: list[str]) -> dict[str, Any]:
    ticker = decision_state.compact(decision.get("ticker")).upper()
    condition = candidate["text"]
    compound = _is_compound_condition(condition)
    # A price plus a factual gate is not a price-only executable trigger.  Do
    # not add a new type here: keep the existing condition rule type and let
    # the review flag prevent a false interpretation of the price fragment.
    rule_type = "EVENT" if candidate["type"] == "EVENT" and not _METRIC_RE.search(condition) else "METRIC" if compound else candidate["type"]
    low = None if compound else candidate["min"]
    high = None if compound else candidate["max"]
    currency = None if compound else candidate["currency"]
    source = f"semantic_report:{candidate['line_start']}"
    item = {
        "rule_id": decision_state._rule_id(ticker, rule_type, condition, source),
        "type": rule_type,
        "condition": condition,
        "operator": "between" if low is not None and high is not None else "lte" if high is not None else "gte" if low is not None else None,
        "min": low,
        "max": high,
        "currency": currency,
        "action": _action(candidate["scope"]),
        "automation": "REVIEW",
        "status": "unknown",
        "last_checked": None,
        "source_report": decision.get("report_path"),
        "source_section": f"主报告正文 · {candidate['section']}",
        "confidence": "medium",
        "needs_review": compound,
        "source": "semantic_report",
        "extraction_stage": "semantic",
        "extraction_method": "decision_condition_and_action;compound_condition_needs_manual_review" if compound else "decision_condition_and_action",
        "source_excerpt": _source_excerpt(lines, candidate["line_start"], candidate["line_end"]),
        "rule_scope": candidate["scope"],
    }
    return item


def _same_rule(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a = re.sub(r"\s+", "", decision_state.compact(left.get("condition"))).lower()
    b = re.sub(r"\s+", "", decision_state.compact(right.get("condition"))).lower()
    if a == b:
        return True
    # A semantic sentence often contains the structured condition plus an
    # explanatory tail.  Do not duplicate it when most meaningful tokens match.
    tokens_a = {token for token in re.split(r"[，,；;。\s]+", a) if len(token) >= 3}
    tokens_b = {token for token in re.split(r"[，,；;。\s]+", b) if len(token) >= 3}
    return bool(tokens_a and tokens_b and len(tokens_a & tokens_b) >= 3 and min(len(tokens_a), len(tokens_b)) <= 5)


def _normalise_fact_text(text: str) -> str:
    """Remove wording differences without erasing thresholds or direction."""
    value = decision_state.compact(text).lower()
    value = value.replace("两个", "2").replace("两", "2").replace("一季度", "1季度")
    value = value.replace("半年报", "半年度报告").replace("中报", "半年度报告")
    value = value.replace("季度", "期").replace("季", "期")
    value = value.replace("回升至", "改善至").replace("恢复至", "改善至").replace("企稳", "改善")
    value = value.replace("下降至", "低于").replace("降至", "低于")
    value = value.replace("经营性现金流", "经营现金流")
    # Use placeholders so a canonical token such as ``penetration`` is not
    # matched again by the later PE/PS alias.
    placeholders: dict[str, str] = {}
    for index, (canonical, pattern) in enumerate(_FACT_ALIASES):
        placeholder = f"§{index}§"
        value = re.sub(pattern, placeholder, value, flags=re.I)
        placeholders[placeholder] = canonical
    for placeholder, canonical in placeholders.items():
        value = value.replace(placeholder, canonical)
    value = value.replace("以下", "低于").replace("以上", "高于")
    # These words explain why the condition matters, but do not identify a
    # different fact.  Keeping comparators, numbers, time windows and named
    # entities prevents opposite or genuinely different triggers from being
    # merged.
    value = re.sub(
        r"(?:若|如果|只有|除非|一旦|当|则|那么|因此|需要|还需|等待|等到|等候|确认|验证|显示|"
        r"后重新(?:评估|审视|估值|复核)|重新(?:评估|审视|估值|复核)|可以考虑|才考虑|进入买入|"
        r"提供安全边际|值得考虑|明显|继续|再次|正式|当前|后续)",
        "",
        value,
    )
    return re.sub(r"[\s，,；;。！？!?：:（）()\[\]{}]+", "", value)


def _fact_signature(text: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    value = _normalise_fact_text(text)
    atoms = tuple(sorted({canonical for canonical, _ in _FACT_ALIASES if canonical in value}))
    numbers = tuple(re.findall(r"\d+(?:\.\d+)?", value))
    directions = tuple(sorted(set(re.findall(r"不低于|不高于|低于|高于|以下|以上|超过|达到|改善|下降|上升|稳定|负|正|恶化|放缓|回落|回升", value))))
    named = tuple(sorted(set(re.findall(r"[a-z][a-z0-9+.-]*", value))))
    return atoms, numbers, directions, named


def _same_fact(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return true only for the same underlying fact, not just same scope."""
    left_signature = _fact_signature(decision_state.compact(left.get("condition")))
    right_signature = _fact_signature(decision_state.compact(right.get("condition")))
    if not left_signature[0] or left_signature[0] != right_signature[0]:
        return False
    if left_signature[1:] != right_signature[1:]:
        # “硅碳渗透提高而产品缺乏竞争力” and the same redline with an
        # explicit 40% threshold are the same business fact, with the latter
        # simply being more specific.  Preserve the more specific wording
        # during merge; do not generalize this exception to unrelated OCF,
        # margin or leverage thresholds.
        if set(left_signature[0]) != {"competitiveness", "penetration"}:
            return False
        if left_signature[3] != right_signature[3] or (left_signature[1] and right_signature[1] and left_signature[1] != right_signature[1]):
            return False
    return True


def _same_consolidation_fact(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("rule_scope") != right.get("rule_scope"):
        return False
    if left.get("action") != right.get("action") or left.get("type") != right.get("type"):
        return False
    return _same_fact(left, right)


def _price_interval(rule: dict[str, Any]) -> tuple[float, float] | None:
    """Use report wording for open/near price bounds during deduplication."""
    if rule.get("type") not in {"PRICE", "PRICE_RANGE"} and not _is_compound_condition(rule.get("condition", "")):
        return None
    condition = decision_state.compact(rule.get("condition"))
    values = list(_NUMBER_RE.finditer(condition))
    low = rule.get("min")
    high = rule.get("max")
    try:
        low = float(low) if low is not None else None
    except (TypeError, ValueError):
        low = None
    try:
        high = float(high) if high is not None else None
    except (TypeError, ValueError):
        high = None
    selected = None
    price_starts = [match.end() for match in _ACTIONABLE_PRICE_RE.finditer(condition)]
    for match in values:
        if any(0 <= match.start() - start <= 32 for start in price_starts):
            selected = match
            break
        if re.match(r"\s*(?:元|港元|港币|HK\$|人民币|美元|USD)", condition[match.end():], re.I):
            selected = match
            break
    if selected is None and values and not price_starts:
        selected = values[0]
    if selected is not None:
        first, second = selected.groups()
        text_low = float(first)
        text_high = float(second) if second else None
        if re.search(r"附近", condition) and text_high is None:
            return text_low, text_low
        if re.search(r"低于|以下|不高于|跌破", condition):
            return float("-inf"), text_low
        if re.search(r"高于|以上|不低于|站上", condition):
            return text_low, float("inf")
        if text_high is not None:
            return text_low, text_high
    if low is not None and high is not None:
        return low, high
    if high is not None:
        return float("-inf"), high
    if low is not None:
        return low, float("inf")
    return None


def _rule_currency(rule: dict[str, Any]) -> str:
    currency = decision_state.compact(rule.get("currency")).upper()
    if currency:
        return currency
    condition = decision_state.compact(rule.get("condition"))
    if re.search(r"港元|港币|HK\$", condition, re.I):
        return "HKD"
    if re.search(r"美元|USD|\$", condition, re.I):
        return "USD"
    if re.search(r"元|人民币|CNY|RMB", condition, re.I):
        return "CNY"
    return "UNKNOWN"


def _is_compound_condition(text: str) -> bool:
    """Detect a condition with more than a price/threshold atom.

    This is a safety classification for consolidation.  It does not create a
    new Rule type: a compound candidate remains one existing METRIC/EVENT Rule
    and is marked for review so a price fragment cannot become a standalone
    trigger.
    """
    value = decision_state.compact(text)
    if not (_ACTIONABLE_PRICE_RE.search(value) or re.search(r"\d+(?:\.\d+)?\s*(?:元|港元|港币|HK\$|美元|USD)", value, re.I)):
        return False
    if not _COMPOUND_JOIN_RE.search(value):
        return False
    remainder = re.sub(
        r"(?:股价|股票价格|价格|价位|回调至|回落至|跌入|跌破|低于|不高于|不超过|高于|不低于|不超过|"
        r"进入|接近|附近|\d+(?:\.\d+)?\s*(?:—|–|-)?\s*\d*(?:\.\d+)?\s*(?:元|港元|港币|HK\$|人民币|美元|USD)?)",
        "",
        value,
        flags=re.I,
    )
    remainder = re.sub(r"安全边际|性价比|风险收益比|买入窗口|估值太贵|估值过高|估值合理", "", remainder)
    return bool(_COMPOUND_FACT_RE.search(remainder))


def _hard_compound_condition(text: str) -> bool:
    if not _is_compound_condition(text):
        return False
    # These are genuine factual gates.  A weak phrase such as “基本面未坏”
    # can be shown as a tier in a price review; an OCF/quarter/order/valuation
    # threshold must not be silently reduced to a price-only trigger.
    if _WEAK_PRICE_QUALIFIER_RE.fullmatch(decision_state.compact(text)):
        return False
    return bool(re.search(
        r"季度|半年报|年报|业绩|现金流|OCF|FCF|ROE|ROIC|毛利率|订单|回款|付款|到账|利用率|资本开支|"
        r"负债|净债务|EBITDA|PS|PE|PB|估值|产量|进度|政策|铜价|流动性|分红|利润|竞争|回报|业务|客户",
        text,
        re.I,
    ))


def _valuation_only_price_compound(text: str) -> bool:
    """Whether a price conjunction adds only a valuation qualifier."""
    if not _hard_compound_condition(text):
        return True
    remainder = re.sub(
        r"(?:股价|股票价格|价格|价位|回调至|回落至|跌入|跌破|低于|不高于|不超过|高于|不低于|"
        r"进入|接近|附近|PE|PS|PB|估值|安全边际|风险收益比|买入窗口|\d+(?:\.\d+)?\s*(?:—|–|-)?\s*\d*(?:\.\d+)?\s*(?:元|港元|港币|HK\$|人民币|美元|USD|倍|x)?)",
        "",
        decision_state.compact(text),
        flags=re.I,
    )
    remainder = re.sub(r"基本面未(?:坏|恶化)|基本面(?:稳定|未明显恶化)|业绩未恶化", "", remainder)
    return not _OPERATING_GATE_RE.search(remainder)


def _merge_source_excerpts(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    excerpts = [item.get("source_excerpt") for item in items if isinstance(item.get("source_excerpt"), dict)]
    if not excerpts:
        return None
    texts = []
    for excerpt in excerpts:
        text = decision_state.compact(excerpt.get("text"))
        if text and text not in texts:
            texts.append(text)
    starts = [item.get("line_start") for item in excerpts if isinstance(item.get("line_start"), int)]
    ends = [item.get("line_end") for item in excerpts if isinstance(item.get("line_end"), int)]
    return {
        "line_start": min(starts) if starts else None,
        "line_end": max(ends) if ends else None,
        "text": " | ".join(texts),
    }


def _merge_rule_group(items: list[dict[str, Any]], *, price_group: bool = False) -> dict[str, Any]:
    """Merge a confirmed semantic duplicate group without changing schema."""
    structured = [item for item in items if item.get("extraction_stage") == "structured"]
    base = copy.deepcopy(structured[0] if structured else max(items, key=lambda item: len(decision_state.compact(item.get("condition")))))
    conditions = []
    for item in sorted(items, key=lambda value: (value.get("line_start") or 0, value.get("rule_id") or "")):
        condition = decision_state.compact(item.get("condition"))
        if condition and condition not in conditions:
            conditions.append(condition)
    if price_group:
        intervals = [_price_interval(item) for item in items]
        finite_lows = [value[0] for value in intervals if value and value[0] != float("-inf")]
        finite_highs = [value[1] for value in intervals if value and value[1] != float("inf")]
        currency = next((item.get("currency") for item in items if item.get("currency")), None)
        if finite_lows and finite_highs:
            low, high = min(finite_lows), max(finite_highs)
            unit = {"HKD": "港元", "CNY": "元", "USD": "美元"}.get(currency, "")
            lead = f"股价进入 {low:g}–{high:g}{unit} 区间"
            base["type"] = "PRICE_RANGE"
            base["operator"] = "between"
            base["min"] = low
            base["max"] = high
            base["currency"] = currency
        else:
            lead = conditions[0] if conditions else "价格条件"
        # Keep a price ladder and its meaningful qualifiers auditable, while
        # removing repeated wording for the same interval.  A qualified
        # interval wins over its unqualified duplicate (e.g. “10–11 元且
        # 基本面未坏” over “回落至 10–11 元”).
        selected: dict[tuple[Any, ...], tuple[bool, str]] = {}
        for item in sorted(items, key=lambda value: (value.get("line_start") or 0, value.get("rule_id") or "")):
            condition = decision_state.compact(item.get("condition"))
            interval = _price_interval(item)
            if not condition or interval is None:
                continue
            weak_qualifier = bool(re.search(r"基本面|未恶化|未坏|安全边际|估值", condition))
            near = "near" if "附近" in condition else "band"
            key = (near, interval[0], interval[1])
            existing = selected.get(key)
            if existing is None or (weak_qualifier and not existing[0]) or len(condition) > len(existing[1]):
                selected[key] = (weak_qualifier, condition)
        qualifiers = []
        lead_interval = (min(finite_lows), max(finite_highs)) if finite_lows and finite_highs else None
        for key, (is_qualified, condition) in selected.items():
            if lead_interval is not None and key[0] == "band" and key[1:] == lead_interval and not is_qualified:
                continue
            if condition == lead or (lead.startswith("股价进入") and condition.replace(" ", "") in lead.replace(" ", "")):
                continue
            if condition not in qualifiers:
                qualifiers.append(condition)
        base["condition"] = lead if not qualifiers else lead + "；" + "；".join(qualifiers)
    else:
        # Prefer the structured wording for its confidence/fields, unless the
        # semantic sentence carries materially more context.
        base["condition"] = max(conditions, key=len) if conditions else base.get("condition")
    hard_compound = any(_hard_compound_condition(condition) for condition in conditions)
    if price_group and not hard_compound and _hard_compound_condition(base.get("condition", "")):
        hard_compound = not _valuation_only_price_compound(base.get("condition", ""))
    if hard_compound:
        # A PRICE type would be evaluated from the quote alone.  Keeping the
        # existing METRIC/EVENT type and clearing price fields makes the
        # unresolved conjunction visible without allowing a false PRE_BUY.
        if _hard_compound_condition(base.get("condition", "")) or any(_hard_compound_condition(condition) for condition in conditions):
            base["type"] = "EVENT" if _EVENT_RE.search(base.get("condition", "")) and not _METRIC_RE.search(base.get("condition", "")) else "METRIC"
            base["operator"] = None
            base["min"] = None
            base["max"] = None
            base["currency"] = None
        base["needs_review"] = True
        base["automation"] = "REVIEW"
        method = decision_state.compact(base.get("extraction_method"))
        if "compound_condition_needs_manual_review" not in method:
            base["extraction_method"] = (method + ";" if method else "") + "compound_condition_needs_manual_review"
    confidence_order = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
    base["confidence"] = max(
        (item.get("confidence") or "unknown" for item in items),
        key=lambda value: confidence_order.get(value, 0),
    )
    base["source_excerpt"] = _merge_source_excerpts(items) or base.get("source_excerpt")
    if len(items) > 1:
        method = decision_state.compact(base.get("extraction_method"))
        if "semantic_consolidation" not in method:
            base["extraction_method"] = (method + ";" if method else "") + "semantic_consolidation"
    ticker = decision_state.compact(base.get("rule_id", "")).split(":", 1)[0].upper()
    base["rule_id"] = decision_state._rule_id(
        ticker,
        base.get("type", "METRIC"),
        decision_state.compact(base.get("condition")),
        "consolidated:" + decision_state.compact(base.get("rule_scope")),
    )
    return base


def _split_independent_redline_alternatives(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split explicit redline alternatives when either fact can act alone."""
    result: list[dict[str, Any]] = []
    for item in rules:
        condition = decision_state.compact(item.get("condition"))
        if item.get("rule_scope") != "redline" or "或" not in condition or re.search(r"且|并且|同时", condition):
            result.append(item)
            continue
        parts = _split_redline_list(condition)
        if len(parts) < 2 or not all(
            _HARD_CONDITION_RE.search(part) or _METRIC_RE.search(part) or _EVENT_RE.search(part)
            for part in parts
        ):
            result.append(item)
            continue
        ticker = decision_state.compact(item.get("rule_id", "")).split(":", 1)[0].upper()
        for index, part in enumerate(parts, 1):
            clone = copy.deepcopy(item)
            clone["condition"] = _strip_rule_label(part)
            clone["type"] = _rule_type(clone["condition"])
            clone["operator"] = None
            clone["min"], clone["max"], clone["currency"] = _price_fields(clone["condition"], None)
            clone["rule_id"] = decision_state._rule_id(
                ticker,
                clone["type"],
                clone["condition"],
                f"{clone.get('source', 'redline')}:alternative:{index}",
            )
            result.append(clone)
    return result


def consolidate_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Consolidate only same-fact/same-action duplicates.

    Price intervals are grouped only when they overlap.  Non-price rules need
    the same scope, action, type and fact signature.  Distinct redlines and
    unresolved conjunctions therefore remain separate.
    """
    rules = [
        rule for rule in rules
        if not _NON_RULE_LABEL_RE.fullmatch(decision_state.compact(rule.get("condition")))
    ]
    if len(rules) < 2:
        return rules
    consumed: set[int] = set()
    groups: list[tuple[list[int], bool]] = []

    price_indices = [
        index for index, rule in enumerate(rules)
        if rule.get("rule_scope") == "entry"
        and rule.get("action") == "review_decision"
        and (
            rule.get("type") in {"PRICE", "PRICE_RANGE"}
            or _is_compound_condition(rule.get("condition", ""))
        )
    ]
    for index in price_indices:
        if index in consumed:
            continue
        interval = _price_interval(rules[index])
        if interval is None:
            continue
        currency = _rule_currency(rules[index])
        group = [index]
        changed = True
        while changed:
            changed = False
            for other in price_indices:
                if other in group or other in consumed:
                    continue
                if _rule_currency(rules[other]) != currency:
                    continue
                other_interval = _price_interval(rules[other])
                if other_interval is None:
                    continue
                overlaps = any(
                    _price_interval(rules[item])
                    and not (
                        _price_interval(rules[item])[1] < other_interval[0]
                        or other_interval[1] < _price_interval(rules[item])[0]
                    )
                    for item in group
                )
                if not overlaps:
                    continue
                candidate_items = [rules[item] for item in group + [other]]
                hard = any(_hard_compound_condition(item.get("condition", "")) for item in candidate_items)
                if hard and not all(
                    _valuation_only_price_compound(item.get("condition", ""))
                    for item in candidate_items
                    if _is_compound_condition(item.get("condition", ""))
                ):
                    # A price plus an operating gate is not the same trigger
                    # as a price-only entry.  Leave it for manual review.
                    continue
                group.append(other)
                changed = True
        if len(group) > 1:
            consumed.update(group)
            groups.append((group, True))

    nonprice_indices = [index for index in range(len(rules)) if index not in consumed]
    by_key: list[list[int]] = []
    for index in nonprice_indices:
        rule = rules[index]
        if rule.get("type") not in {"METRIC", "EVENT"}:
            continue
        if not _fact_signature(decision_state.compact(rule.get("condition")))[0]:
            continue
        for group in by_key:
            if _same_consolidation_fact(rule, rules[group[0]]):
                group.append(index)
                break
        else:
            by_key.append([index])
    for group in by_key:
        if len(group) > 1:
            consumed.update(group)
            groups.append((group, False))

    if not groups:
        return rules
    merged_by_first = {min(indices): _merge_rule_group([rules[index] for index in indices], price_group=price_group) for indices, price_group in groups}
    result = []
    for index, rule in enumerate(rules):
        if index in merged_by_first:
            result.append(merged_by_first[index])
        if index in consumed:
            continue
        result.append(rule)
    return result


def extract_company(decision: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    report_value = decision.get("report_path")
    report_path = (repo_root / str(report_value)).resolve() if report_value else None
    if report_path is None or repo_root.resolve() not in report_path.parents or not report_path.is_file():
        return {
            "rules": [],
            "monitoring_metrics": [],
            "semantic_review_candidates": [],
            "rule_extraction_status": "extraction_failed",
            "zero_rule_reason": "extraction_failed",
            "extraction_error": "canonical_report_missing_or_unreadable",
        }
    try:
        lines = report_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        return {
            "rules": [],
            "monitoring_metrics": [],
            "semantic_review_candidates": [],
            "rule_extraction_status": "extraction_failed",
            "zero_rule_reason": "extraction_failed",
            "extraction_error": str(error),
        }
    structured = _split_structured_redline_compounds(
        decision,
        _structured_rules(decision, lines),
        lines,
    )
    semantic_candidates, metrics, review_candidates = _semantic_candidates(lines, decision.get("market"))
    semantic_rules: list[dict[str, Any]] = []
    for candidate in semantic_candidates:
        item = _semantic_rule(decision, candidate, lines)
        if not any(_same_rule(item, existing) for existing in structured + semantic_rules):
            semantic_rules.append(item)
    # Structured compound gates are canonical evidence.  They must not be
    # discarded merely because semantic clauses overlap with part of them;
    # consolidation below can merge a true duplicate without splitting the
    # original conjunction into independent triggers.
    rules = structured + semantic_rules
    deduped: dict[str, dict[str, Any]] = {item["rule_id"]: item for item in rules}
    rules = _split_independent_redline_alternatives(list(deduped.values()))
    rules = consolidate_rules(rules)
    for rule in rules:
        rule.update(
            source_metadata_for_excerpt(
                report_path,
                lines,
                rule.get("source_excerpt"),
                rule.get("condition", ""),
            )
        )
    has_semantic = any(item.get("extraction_stage") == "semantic" for item in rules)
    if rules:
        status = "structured_and_semantic" if structured and has_semantic else "semantic_extracted" if has_semantic else "structured_extracted"
        zero_reason = None
    elif review_candidates:
        status = "needs_semantic_review"
        zero_reason = "needs_semantic_review"
    else:
        status = "no_explicit_decision_rule"
        zero_reason = "no_explicit_decision_rule"
    return {
        "rules": rules,
        "monitoring_metrics": _dedupe_monitoring_metrics(metrics),
        "semantic_review_candidates": review_candidates,
        "rule_extraction_status": status,
        "zero_rule_reason": zero_reason,
        "extraction_error": None,
    }


def build_payload(decisions: Iterable[dict[str, Any]], repo_root: Path, *, generated_at: str | None = None, previous_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    decisions = list(decisions)
    generated_at = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    companies: list[dict[str, Any]] = []
    previous_audit = (previous_payload or {}).get("zero_rule_audit") or {}
    previous_zero = {
        decision_state.compact(ticker).upper()
        for ticker in previous_audit.get("previous_zero_rule_tickers", [])
        if decision_state.compact(ticker)
    }
    if not previous_zero:
        previous_zero = {
            decision_state.compact(item.get("ticker")).upper()
            for item in (previous_payload or {}).get("companies", [])
            if isinstance(item, dict) and item.get("market") == "港股" and not item.get("rules")
        }
    legacy_zero = {
        decision_state.compact(item.get("ticker")).upper()
        for item in decisions
        if item.get("market") == "港股" and not decision_state._rules_for_decision(item)
    }
    if not previous_audit.get("baseline_locked") and len(legacy_zero) > len(previous_zero):
        # Repair an intermediate payload created before the baseline ticker
        # list was persisted.  Once written, the legacy cohort is locked and
        # later migrations keep comparing against the same 93-company base.
        previous_zero = legacy_zero
    for decision in decisions:
        extracted = extract_company(decision, repo_root)
        ticker = decision_state.compact(decision.get("ticker")).upper()
        cid = decision_state.company_id(decision)
        summary = {
            "total": len(extracted["rules"]),
            "entry": sum(rule.get("rule_scope") == "entry" for rule in extracted["rules"]),
            "validation": sum(rule.get("rule_scope") == "validation" for rule in extracted["rules"]),
            "redline": sum(rule.get("rule_scope") == "redline" for rule in extracted["rules"]),
            "monitoring_metric_count": len(extracted["monitoring_metrics"]),
            "semantic_review_candidate_count": len(extracted["semantic_review_candidates"]),
        }
        companies.append({
            "company_id": cid,
            "company": decision.get("company"),
            "ticker": ticker or None,
            "market": decision.get("market") or "unknown",
            "realtime_scope": "supported" if decision.get("market") in decision_state.REALTIME_MARKETS else "research_only",
            "canonical_report": decision.get("report_path") or None,
            "rules": extracted["rules"],
            "monitoring_metrics": extracted["monitoring_metrics"],
            "semantic_review_candidates": extracted["semantic_review_candidates"],
            "rule_extraction_status": extracted["rule_extraction_status"],
            "zero_rule_reason": extracted["zero_rule_reason"],
            "extraction_error": extracted["extraction_error"],
            "summary": summary,
        })
    zero_companies = [item for item in companies if not item["rules"]]
    hk_zero = [item for item in zero_companies if item.get("market") == "港股"]
    former_zero = [item for item in companies if item.get("ticker") in previous_zero]
    scope_summary: dict[str, dict[str, Any]] = {}
    for scope_name, scoped in {
        "A股": [item for item in companies if item.get("market") == "A股"],
        "港股": [item for item in companies if item.get("market") == "港股"],
        "research_only": [item for item in companies if item.get("market") not in decision_state.REALTIME_MARKETS],
    }.items():
        scoped_rules = [rule for item in scoped for rule in item.get("rules") or []]
        scope_summary[scope_name] = {
            "company_count": len(scoped),
            "rule_count": len(scoped_rules),
            "zero_rule_company_count": sum(not item.get("rules") for item in scoped),
            "entry": sum(rule.get("rule_scope") == "entry" for rule in scoped_rules),
            "validation": sum(rule.get("rule_scope") == "validation" for rule in scoped_rules),
            "redline": sum(rule.get("rule_scope") == "redline" for rule in scoped_rules),
        }
    audit = {
        "scope": "A股 + 港股",
        "current_zero_rule_company_count": len(hk_zero),
        "previous_zero_rule_company_count": len(previous_zero),
        "previous_zero_rule_tickers": sorted(previous_zero),
        "baseline_locked": True,
        "true_zero_rule": sum(item.get("zero_rule_reason") == "no_explicit_decision_rule" for item in hk_zero),
        "semantic_extracted": sum(item.get("rule_extraction_status") in {"semantic_extracted", "structured_and_semantic"} for item in former_zero),
        "needs_semantic_review": sum(item.get("zero_rule_reason") == "needs_semantic_review" for item in hk_zero),
        "extraction_failed": sum(item.get("zero_rule_reason") == "extraction_failed" for item in hk_zero),
        "former_zero_rule_status_counts": dict(Counter(item.get("rule_extraction_status") for item in former_zero)),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "rule_types": list(decision_state.RULE_TYPES),
        "automation_levels": list(decision_state.AUTOMATION_LEVELS),
        "companies": companies,
        "rule_count": sum(len(item.get("rules") or []) for item in companies),
        "scope_summary": scope_summary,
        "quality_dimensions": {
            "extraction_confidence": "rules[].confidence (structured/semantic extraction quality; not action automation)",
            "automation_level": "rules[].automation (AUTO/REVIEW/MANUAL execution capability)",
            "current_rule_status": "rules[].status (current facts/quote evaluation)",
            "rule_manual_review_flag": "rules[].needs_review (legacy per-rule operational review flag)",
            "semantic_review_queue": "companies[].semantic_review_candidates (body meaning not safely normalized)",
            "zero_rule_reason": "companies[].zero_rule_reason (only when rules is empty)",
        },
        "extraction_policy": {
            "structured_fast_path": "execution_policy and explicit report fields",
            "semantic_second_pass": "canonical report body condition plus action language",
            "monitoring_metric_policy": "ordinary watch-list metrics are never promoted without an action-changing condition",
            "zero_rule_reasons": ["no_explicit_decision_rule", "extraction_failed", "needs_semantic_review"],
            "builder_contract": "load, merge, sort, render; no semantic extraction",
        },
        "zero_rule_audit": audit,
    }


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--board", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="report extraction counts without writing the payload")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.dry_run and args.write:
        parser.error("choose --dry-run or --write")
    root = args.repo_root.resolve()
    board_path = (args.board or root / "data/investment-dashboard/decision_board.json").resolve()
    board = json.loads(board_path.read_text(encoding="utf-8"))
    previous = decision_state.load_json(root / "data/investment-dashboard/decision_rules.json", {})
    payload = build_payload(board.get("decisions", []), root, previous_payload=previous)
    if args.write:
        decision_state.write_json(
            root / "data/investment-dashboard/decision_rules.json",
            decision_state.rule_definition_payload(payload),
        )
    print(json.dumps({"mode": "write" if args.write else "dry-run", **payload["zero_rule_audit"], "rule_count": payload["rule_count"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
