import json, subprocess, pathlib, sys
results = [
  {"id":4,"label":"行业格局与竞争 · 评分","reported_value":4.0,"unit":"","fetched_value":None,"fetched_source":"主观评分，非外部可取数","fetched_value2":None,"fetched_source2":""},
  {"id":5,"label":"风险、治理与长期确定性 · 评分","reported_value":4.0,"unit":"","fetched_value":None,"fetched_source":"主观评分，非外部可取数","fetched_value2":None,"fetched_source2":""},
  {"id":12,"label":"归母净利润 · 2026Q1","reported_value":2.71,"unit":"亿元","fetched_value":2.7066553647,"fetched_source":"四方股份2026Q1报告","fetched_value2":2.7066553647,"fetched_source2":"东方财富/AkShare"},
  {"id":15,"label":"扣非净利润 · 2025","reported_value":8.00,"unit":"亿元","fetched_value":8.0018495603,"fetched_source":"四方股份2025年报","fetched_value2":8.00185,"fetched_source2":"东方财富/AkShare"},
  {"id":14,"label":"扣非净利润 · 2024","reported_value":6.98,"unit":"亿元","fetched_value":6.9798621123,"fetched_source":"四方股份2025年报上年数","fetched_value2":6.979862,"fetched_source2":"东方财富/AkShare"},
  {"id":18,"label":"经营现金流 · 2025","reported_value":12.25,"unit":"亿元","fetched_value":12.2465646311,"fetched_source":"四方股份2025年报","fetched_value2":12.24656,"fetched_source2":"东方财富/AkShare"},
  {"id":29,"label":"电网自动化 · 收入占比","reported_value":45.0,"unit":"%","fetched_value":44.97,"fetched_source":"2025年报分产品收入/主营收入计算","fetched_value2":44.90,"fetched_source2":"年报分产品收入/总营业收入计算"},
  {"id":32,"label":"电厂及工业自动化 · 收入占比","reported_value":46.8,"unit":"%","fetched_value":46.77,"fetched_source":"2025年报分产品收入/主营收入计算","fetched_value2":46.70,"fetched_source2":"年报分产品收入/总营业收入计算"},
  {"id":36,"label":"其他 · 毛利率","reported_value":11.60,"unit":"%","fetched_value":11.60,"fetched_source":"四方股份2025年报分产品表","fetched_value2":11.60,"fetched_source2":"本地PDF抽取"},
  {"id":55,"label":"P/FCF TTM · 数值","reported_value":59.5,"unit":"x","fetched_value":59.52,"fetched_source":"市值507.86亿元/TTM FCF 8.53亿元计算","fetched_value2":59.5,"fetched_source2":"financial-analyst复核"},
  {"id":70,"label":"熊市 · 合理倍数","reported_value":15.0,"unit":"","fetched_value":None,"fetched_source":"估值情景假设，非外部可取数","fetched_value2":None,"fetched_source2":""},
  {"id":76,"label":"基准 · 合理股价","reported_value":24.0,"unit":"","fetched_value":None,"fetched_source":"估值情景计算区间下限，非外部信源取数","fetched_value2":None,"fetched_source2":""},
  {"id":82,"label":"2025营业收入 · 来源2","reported_value":81.9331,"unit":"亿元","fetched_value":81.9331011395,"fetched_source":"四方股份2025年报","fetched_value2":81.933101,"fetched_source2":"东方财富/AkShare"},
  {"id":87,"label":"2026Q1归母净利润 · 来源1","reported_value":2.7067,"unit":"亿元","fetched_value":2.7066553647,"fetched_source":"四方股份2026Q1报告","fetched_value2":2.706655,"fetched_source2":"东方财富/AkShare"},
]
path = pathlib.Path('reports/四方股份/audit_results_20260707.json')
path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(path.resolve())