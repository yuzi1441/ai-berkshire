import json, pathlib, subprocess, sys, os
results=[
 {"id":4,"label":"东方电子2026Q1扣非净利率","reported_value":8.26,"unit":"%","fetched_value":8.26,"fetched_source":"AKShare财务摘要/peer_metrics.csv: 2026Q1扣非净利润1.2540605456亿元 / 营业收入15.1893434619亿元","fetched_value2":8.26,"fetched_source2":"巨潮2026一季报: 扣非1.2540605456亿元 / 收入15.1893434619亿元"},
 {"id":1,"label":"东方电子2025收入","reported_value":83.77,"unit":"亿元","fetched_value":83.774828874,"fetched_source":"巨潮2025年报: 营业收入8,377,482,887.40元","fetched_value2":83.77483,"fetched_source2":"AKShare财务摘要: 20251231营业总收入8.377483e9元"},
 {"id":8,"label":"国电南瑞2026Q1扣非净利率","reported_value":6.71,"unit":"%","fetched_value":6.71,"fetched_source":"AKShare财务摘要/peer_metrics.csv: 扣非6.4198634523亿元 / 收入95.64243亿元","fetched_value2":6.71,"fetched_source2":"peer_metrics.csv同业表导出"},
 {"id":9,"label":"许继电气2025收入","reported_value":149.92,"unit":"亿元","fetched_value":149.9191,"fetched_source":"AKShare财务摘要/peer_metrics.csv: 20251231营业总收入1.499191e10元","fetched_value2":149.92,"fetched_source2":"peer_metrics.csv同业表导出"},
 {"id":21,"label":"股息率","reported_value":0.40,"unit":"%","fetched_value":0.4042,"fetched_source":"计算: 2025分红每股0.05元 / 腾讯行情2026-07-06收盘价12.37元","fetched_value2":0.40,"fetched_source2":"financial_rigor_outputs.txt: 股息率 0.05 / 12.37 = 0.40%"}
]
p=pathlib.Path('sources')/'东方电子'/'audit_results_final_article.json'
p.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(p)
print(json.dumps(results,ensure_ascii=False))