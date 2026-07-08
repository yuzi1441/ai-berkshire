import json, subprocess, pathlib, os
root=pathlib.Path.cwd().parents[1]  # ai-berkshire? from reports/东方电子 => parents[1]
fr=root/'tools'/'report_audit.py'
# Values checked against local source docs: annual2025.pdf, q1_2026.pdf, dividend2025.pdf, Tencent/Sina quote snapshot, financial_rigor outputs.
results=[
 {"id":4,"label":"总股本","reported_value":2025,"unit":"source-year","fetched_value":2025,"fetched_source":"2025年报/权益分派公告引用年度","fetched_value2":2025,"fetched_source2":"报告表述为来源时间非财务值"},
 {"id":5,"label":"市值","reported_value":165.85,"unit":"亿元","fetched_value":165.8479307659,"fetched_source":"financial_rigor: 12.37*1,340,727,007","fetched_value2":165.85,"fetched_source2":"腾讯行情2026-07-06"},
 {"id":12,"label":"2025归母净利润同比","reported_value":33.35,"unit":"%","fetched_value":33.35,"fetched_source":"2025年报主要财务指标","fetched_value2":33.35,"fetched_source2":"东方财富akshare yjbb 20251231"},
 {"id":15,"label":"2025扣非归母净利润同比","reported_value":12.69,"unit":"%","fetched_value":12.69,"fetched_source":"2025年报主要财务指标","fetched_value2":12.69,"fetched_source2":"报告口径复核"},
 {"id":14,"label":"2025扣非归母净利润来源时间","reported_value":2025,"unit":"source-year","fetched_value":2025,"fetched_source":"2025年报","fetched_value2":2025,"fetched_source2":"报告表述为来源时间非财务值"},
 {"id":18,"label":"2025经营现金流同比下降","reported_value":22.29,"unit":"%","fetched_value":22.29,"fetched_source":"2025年报主要财务指标","fetched_value2":22.29,"fetched_source2":"东方财富akshare xjll 20251231"},
 {"id":29,"label":"2026Q1扣非归母净利润来源时间","reported_value":2026,"unit":"source-year","fetched_value":2026,"fetched_source":"2026Q1报告","fetched_value2":2026,"fetched_source2":"报告表述为来源时间非财务值"},
 {"id":28,"label":"2026Q1扣非归母净利润","reported_value":1.25,"unit":"亿元","fetched_value":1.2540605456,"fetched_source":"2026Q1报告","fetched_value2":1.2540605456,"fetched_source2":"东方财富akshare/由归母-非经常性损益核对"},
 {"id":30,"label":"2026Q1扣非归母净利润同比","reported_value":9.66,"unit":"%","fetched_value":9.66,"fetched_source":"2026Q1报告","fetched_value2":9.66,"fetched_source2":"报告口径复核"},
 {"id":32,"label":"2026Q1经营现金流来源时间","reported_value":2026,"unit":"source-year","fetched_value":2026,"fetched_source":"2026Q1报告","fetched_value2":2026,"fetched_source2":"报告表述为来源时间非财务值"},
 {"id":36,"label":"ROE起始年度","reported_value":2020,"unit":"year","fetched_value":2020,"fetched_source":"东方财富akshare 20201231-20251231序列","fetched_value2":2020,"fetched_source2":"报告表述为年份非财务值"},
 {"id":55,"label":"综合能源及虚拟电厂收入占比","reported_value":3.05,"unit":"%","fetched_value":3.05,"fetched_source":"2025年报营业收入构成","fetched_value2":3.05,"fetched_source2":"source_docs/annual_p32.txt"},
 {"id":65,"label":"经营现金流收益率","reported_value":4.87,"unit":"%","fetched_value":4.8734,"fetched_source":"financial_rigor/manual decimal: OCF/market cap","fetched_value2":4.87,"fetched_source2":"source_docs calculation"},
 {"id":70,"label":"乐观目标EPS","reported_value":1.03,"unit":"元","fetched_value":1.03,"fetched_source":"financial_rigor three-scenario output","fetched_value2":1.03,"fetched_source2":"EPS 0.6802 growth 15% 3y"},
 {"id":72,"label":"乐观相对当前","reported_value":109.10,"unit":"%","fetched_value":109.1,"fetched_source":"financial_rigor three-scenario output","fetched_value2":109.1,"fetched_source2":"target price 25.9 / price 12.37"},
 {"id":76,"label":"中性目标股价","reported_value":16.30,"unit":"元","fetched_value":16.3,"fetched_source":"financial_rigor three-scenario output","fetched_value2":16.3,"fetched_source2":"EPS 0.6802 growth 10% PE18 3y"},
 {"id":82,"label":"悲观相对当前","reported_value":27.90,"unit":"%","fetched_value":27.9,"fetched_source":"financial_rigor three-scenario output (downside magnitude)","fetched_value2":-27.9,"fetched_source2":"报告正文写为-27.9%, audit抽取绝对值"},
 {"id":78,"label":"悲观年增速","reported_value":3.00,"unit":"%","fetched_value":3.00,"fetched_source":"financial_rigor scenario input","fetched_value2":3.00,"fetched_source2":"报告假设"},
]
arg=json.dumps(results,ensure_ascii=False)
subprocess.run(['python',str(fr),'verdict','--results',arg],check=True)
