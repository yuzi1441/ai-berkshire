import json, subprocess, sys
from pathlib import Path
results = [
  {"id":4,"label":"行业格局与长期趋势 · 评分","reported_value":4.3,"unit":"","line_number":40,"fetched_value":4.3,"fetched_source":"四角色行业研究评分汇总；主观分析判断，不适用外部数据库","fetched_value2":4.3,"fetched_source2":"team-lead复核：评分项"},
  {"id":66,"label":"综合评分","reported_value":4.15,"unit":"","line_number":43,"fetched_value":4.15,"fetched_source":"四维评分加权/汇总；主观分析判断，不适用外部数据库","fetched_value2":4.15,"fetched_source2":"team-lead复核：评分项"},
  {"id":7,"label":"营业收入 · 2025","reported_value":862.42,"unit":"亿元","line_number":54,"fetched_value":862.419402222,"fetched_source":"长江电力2025年年度报告/上交所PDF：86,241,940,222.20元","fetched_value2":862.42,"fetched_source2":"东方财富/同花顺财务摘要交叉验证"},
  {"id":9,"label":"归母净利润 · 2024","reported_value":324.96,"unit":"亿元","line_number":55,"fetched_value":324.9617280865,"fetched_source":"长江电力2025年年度报告：2024年归母净利润32,496,172,808.65元","fetched_value2":324.96,"fetched_source2":"东方财富/同花顺财务摘要交叉验证"},
  {"id":15,"label":"经营现金流净额 · 2026Q1 / 2026H1 最新","reported_value":117.11,"unit":"亿元","line_number":56,"fetched_value":117.106630909,"fetched_source":"长江电力2026年第一季度报告：11,710,663,090.90元","fetched_value2":117.11,"fetched_source2":"东方财富/同花顺财务摘要交叉验证"},
  {"id":16,"label":"境内六座电站发电量 · 2024","reported_value":2959.0,"unit":"亿千瓦时","line_number":57,"fetched_value":2958.983,"fetched_source":"由2025年境内六座发电量3071.94亿千瓦时及同比+3.82%反推约2958.91-2959.0；2025年发电量公告/年报","fetched_value2":2959.0,"fetched_source2":"角色报告本地抽取与年报口径复核"},
  {"id":36,"label":"TTM EPS · 数值","reported_value":1.4747,"unit":"元","line_number":71,"fetched_value":1.4747,"fetched_source":"公式：2025 EPS 1.4101 - 2025Q1 EPS 0.2117 + 2026Q1 EPS 0.2763","fetched_value2":1.4747,"fetched_source2":"financial_rigor.py verify-valuation 验算口径"},
  {"id":48,"label":"乐观 · 股价空间（不含股息）","reported_value":45.2,"unit":"%","line_number":202,"fetched_value":45.2,"fetched_source":"financial_rigor.py three-scenario 工具输出；模型结果非外部事实","fetched_value2":45.2,"fetched_source2":"team-lead复核：39.5/27.19-1"},
  {"id":44,"label":"乐观 · 年 EPS 增速","reported_value":6.0,"unit":"%","line_number":202,"fetched_value":6.0,"fetched_source":"情景假设；非外部事实","fetched_value2":6.0,"fetched_source2":"team-lead复核：模型假设项"},
  {"id":60,"label":"已持有、仓位过高 · 价格/条件","reported_value":30.0,"unit":"元","line_number":247,"fetched_value":30.0,"fetched_source":"操作阈值/分析判断；非外部事实","fetched_value2":30.0,"fetched_source2":"team-lead复核：建议阈值项"},
]
Path('reports/长江电力/audit_results_长江电力研究报告-20260707.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(Path('reports/长江电力/audit_results_长江电力研究报告-20260707.json').resolve())
