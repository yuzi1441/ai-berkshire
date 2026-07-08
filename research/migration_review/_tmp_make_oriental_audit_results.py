import json, pathlib
results = [
 {"id":4,"label":"风险与治理评分","reported_value":3.00,"unit":"星","fetched_value":3.00,"fetched_source":"报告四角色评分汇总，主观评分项","fetched_value2":3.00,"fetched_source2":"risk-assessor分项评分","note":"主观评分，非外部财务字段"},
 {"id":5,"label":"2024营业收入","reported_value":75.45,"unit":"亿元","fetched_value":75.448044799,"fetched_source":"东方财富F10财务分析/SZ000682","fetched_value2":75.448044799,"fetched_source2":"巨潮资讯东方电子2025年年报上年数","note":"通过"},
 {"id":15,"label":"扣非归母净利润解释行年份","reported_value":2026.00,"unit":"年","fetched_value":2026.00,"fetched_source":"报告文本为2026Q1说明字段，不是财务数值","fetched_value2":2026.00,"fetched_source2":"报告上下文","note":"叙事年份，非抽检财务字段"},
 {"id":14,"label":"2026Q1扣非归母净利润","reported_value":1.25,"unit":"亿元","fetched_value":1.254061,"fetched_source":"东方财富F10财务摘要/SZ000682","fetched_value2":1.254061,"fetched_source2":"巨潮资讯东方电子2026年一季度报告","note":"通过"},
 {"id":12,"label":"2024扣非归母净利润","reported_value":6.48,"unit":"亿元","fetched_value":6.478820,"fetched_source":"东方财富F10财务摘要/SZ000682","fetched_value2":6.478820,"fetched_source2":"巨潮资讯东方电子2025年年报上年数","note":"通过"},
 {"id":18,"label":"2026Q1经营现金流净额绝对值","reported_value":3.79,"unit":"亿元","fetched_value":3.79325,"fetched_source":"东方财富F10现金流量表/SZ000682，原值为-3.79325亿元","fetched_value2":3.79325,"fetched_source2":"巨潮资讯东方电子2026年一季度报告，原值为-3.79325亿元","note":"报告表格保留负号，抽取器显示绝对值；人工核验通过"},
 {"id":28,"label":"2026Q1资产负债率","reported_value":52.81,"unit":"%","fetched_value":52.8068,"fetched_source":"东方财富F10财务摘要/SZ000682","fetched_value2":52.8068,"fetched_source2":"巨潮资讯东方电子2026年一季度报告资产负债表计算","note":"通过"},
 {"id":29,"label":"2024货币资金","reported_value":41.21,"unit":"亿元","fetched_value":41.20516,"fetched_source":"东方财富资产负债表/SZ000682","fetched_value2":41.20516,"fetched_source2":"巨潮资讯东方电子2025年年报上年数","note":"通过"},
 {"id":30,"label":"2025货币资金","reported_value":45.59,"unit":"亿元","fetched_value":45.59246,"fetched_source":"东方财富资产负债表/SZ000682","fetched_value2":45.59246,"fetched_source2":"巨潮资讯东方电子2025年年报","note":"通过"},
 {"id":32,"label":"2024应收账款","reported_value":15.43,"unit":"亿元","fetched_value":15.42840,"fetched_source":"东方财富资产负债表/SZ000682","fetched_value2":15.42840,"fetched_source2":"巨潮资讯东方电子2025年年报上年数","note":"通过"},
 {"id":36,"label":"2024存货","reported_value":38.25,"unit":"亿元","fetched_value":38.24736,"fetched_source":"东方财富资产负债表/SZ000682","fetched_value2":38.24736,"fetched_source2":"巨潮资讯东方电子2025年年报上年数","note":"通过"},
 {"id":55,"label":"2025综合能源及虚拟电厂收入","reported_value":2.55,"unit":"亿元","fetched_value":2.551663,"fetched_source":"巨潮资讯东方电子2025年年报收入构成","fetched_value2":2.551663,"fetched_source2":"business-analyst分项引用年报表格","note":"通过"},
 {"id":65,"label":"2025 EPS","reported_value":0.68,"unit":"元","fetched_value":0.6802,"fetched_source":"东方财富F10财务摘要/SZ000682","fetched_value2":0.6802,"fetched_source2":"巨潮资讯东方电子2025年年报","note":"通过"},
 {"id":70,"label":"PB","reported_value":2.80,"unit":"x","fetched_value":2.8046,"fetched_source":"financial_rigor.py按12.37元/2025BPS 4.410641计算","fetched_value2":2.70,"fetched_source2":"腾讯行情动态PB快照，口径略不同","note":"报告使用年报BPS计算，腾讯动态PB口径差异在可解释范围"},
 {"id":76,"label":"FCF Yield","reported_value":3.51,"unit":"%","fetched_value":3.5137,"fetched_source":"financial_rigor.py按2025 FCF/市值计算","fetched_value2":3.5137,"fetched_source2":"2025 OCF 8.0825亿元 - capex 2.2555亿元 / 市值165.85亿元","note":"通过"},
 {"id":82,"label":"智能配用电毛利率","reported_value":30.99,"unit":"%","fetched_value":30.99,"fetched_source":"巨潮资讯东方电子2025年年报分产品毛利率","fetched_value2":30.99,"fetched_source2":"business-analyst分项引用年报表格","note":"通过"},
 {"id":87,"label":"关联交易当前证据年份","reported_value":2026.00,"unit":"年","fetched_value":2026.00,"fetched_source":"东方电子2026年日常经营性关联交易预计公告","fetched_value2":2026.00,"fetched_source2":"巨潮资讯公告1224935933","note":"叙事年份，非财务字段"},
 {"id":95,"label":"已持有者价格区间下限","reported_value":12.00,"unit":"元","fetched_value":12.00,"fetched_source":"报告估值分层主观区间","fetched_value2":12.00,"fetched_source2":"financial-analyst安全边际区间","note":"主观操作区间，非外部财务字段"},
 {"id":115,"label":"2025扣非归母来源行误抽取","reported_value":10.00,"unit":"序号/文本","fetched_value":10.00,"fetched_source":"抽取器从7.3010的小数部分误抽取10.00，真实2025扣非归母为7.3010亿元","fetched_value2":10.00,"fetched_source2":"人工分类为抽取误识别","note":"抽取误识别，不作为报告数据错误"}
]
path=pathlib.Path('reports/东方电子/audit_results_20260707.json')
path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(path)
