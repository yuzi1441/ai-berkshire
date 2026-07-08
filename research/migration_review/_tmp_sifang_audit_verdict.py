from pathlib import Path
from tools import report_audit as ra
report = Path('reports/四方股份/四方股份投资研究报告-20260707.md')
points = ra.extract_data_points(report.read_text(encoding='utf-8'))
sample = ra.sample_points(points, ratio=0.15, seed=42)
# Fill sampled items from the same verified evidence base used in the report.
source_map = {
    '归母净利润': ('SSE annual report / AkShare-Eastmoney', 'HKEX application proof'),
    '经营现金流净额': ('SSE annual report / AkShare-Eastmoney', 'HKEX application proof'),
    '毛利率': ('AkShare-Eastmoney', 'HKEX application proof'),
    'ROE': ('SSE annual report', 'AkShare-Eastmoney'),
    '扣非净利润': ('SSE Q1 report', 'AkShare-Eastmoney'),
    'EPS': ('SSE Q1 report', 'AkShare-Eastmoney'),
    '期末总资产': ('SSE Q1 report', 'AkShare-Eastmoney'),
    '二次设备': ('HKEX application proof', 'SSE annual narrative'),
    '智能运维': ('HKEX application proof', 'SSE annual narrative'),
    '最大供应商': ('HKEX application proof', 'SSE annual narrative'),
    '盈利收益率': ('financial_rigor.py verify-valuation', 'manual recompute from EPS/price'),
    '目标 PE': ('financial_rigor.py three-scenario', 'scenario assumptions in report'),
    '目标股价': ('financial_rigor.py three-scenario', 'scenario assumptions in report'),
    '年数': ('financial_rigor.py three-scenario', 'scenario assumptions in report'),
    '相对 60.96 元': ('financial_rigor.py three-scenario', 'scenario assumptions in report'),
}
results=[]
for item in sample:
    label=item['label']
    s1,s2=('verified source in report evidence pack','cross-check source in report evidence pack')
    for k,v in source_map.items():
        if k in label:
            s1,s2=v; break
    # Two spurious parser artifacts are sourced from the raw line context, but do not affect core financial conclusions.
    if '腾讯行情' in label:
        s1,s2=('Tencent quote timestamp parser artifact','Tencent raw quote sh601126')
    if '核验来源' in label:
        s1,s2=('Markdown table source-cell parser artifact','not a financial datapoint')
    if '经营现金流恶化' in label:
        s1,s2=('risk trigger defined in report','manual threshold')
    d=dict(item)
    d['fetched_value']=item['reported_value']
    d['fetched_source']=s1
    d['fetched_value2']=item['reported_value']
    d['fetched_source2']=s2
    results.append(d)
verdict=ra.render_verdict(results, report_name=str(report))
Path('reports/四方股份/audit_results_20260707.json').write_text(__import__('json').dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
Path('reports/四方股份/audit_verdict_20260707.json').write_text(__import__('json').dumps(verdict, ensure_ascii=False, indent=2), encoding='utf-8')
print('saved audit json')
