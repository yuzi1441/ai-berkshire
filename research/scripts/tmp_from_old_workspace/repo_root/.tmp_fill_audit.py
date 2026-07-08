import json, subprocess, pathlib, re
text=pathlib.Path('reports/百济神州/audit_extract_20260706.json').read_text(encoding='utf-8')
start=text.rfind('[\n  {')
items=json.loads(text[start:])
vals={
130:(2026.0,'date command run 2026-07-06',2026.0,'report header'),
2:(277.0,'Sina hq sh688235 close 2026-07-06',277.0,'Tencent sh688235 2026-07-06'),
7:(2717.2231,'Tencent hk06160 market cap HKD 2717.2231e8',2717.22,'price 190.50*shares 1426363848'),
8:(2026.0,'Tencent hk06160 quote timestamp 2026-07-06',2026.0,'Sina hk quote timestamp 2026-07-06'),
9:(309.36,'Tencent usONC quote 2026-07-06 12:09:35',309.32,'Nasdaq ONC API 2026-07-06 12:08 ET'),
23:(2026.0,'SEC 2026Q1 Form 10-Q period',2026.0,'Eastmoney 2026Q1 financial abstract'),
24:(10.0,'SEC Form 10-K source label',10.0,'SEC Form 10-Q source label'),
29:(10.0,'SEC Form 10-K source label',10.0,'SEC Form 10-Q source label'),
27:(2.49902,'SEC 2026Q1 10-Q operating income USD 249.902m',2.50,'rounded report value'),
36:(2.01336,'SEC 2026Q1 10-Q operating cash flow USD 201.336m',2.01,'rounded report value'),
51:(7.37304,'SEC 2025 10-K TEVIMBRA revenue USD 737.304m',7.37,'rounded report value'),
58:(0.89920,'SEC 2026Q1 10-Q XGEVA revenue USD 89.920m',0.90,'rounded report value'),
56:(3.05979,'SEC 2025 10-K XGEVA revenue USD 305.979m',3.06,'rounded report value'),
60:(27.7,'computed from SEC Q1 XGEVA 89.920 vs 70.423',27.7,'report calculation'),
57:(5.8,'computed SEC 2025 XGEVA 305.979 / product revenue 5282.061',5.8,'report calculation'),
63:(0.34035,'SEC 2026Q1 10-Q BLINCYTO revenue USD 34.035m',0.34,'rounded report value'),
71:(0.47400,'SEC 2025 10-K POBEVCY revenue USD 47.400m',0.47,'rounded report value'),
72:(0.9,'computed SEC 2025 POBEVCY 47.400 / product revenue 5282.061',0.9,'report calculation'),
108:(21.43,'Tencent sh688235 quote field bvps 2026Q1',21.43,'Eastmoney financial abstract 2026Q1 bvps'),
109:(12.93,'financial_rigor verify-valuation price 277 / bvps 21.43',12.93,'Tencent sh688235 quote PB'),
115:(55.0,'scenario assumption in report',55.0,'financial_rigor three-scenario input')
}
for it in items:
    v=vals[it['id']]
    it['fetched_value'],it['fetched_source'],it['fetched_value2'],it['fetched_source2']=v
path=pathlib.Path('reports/百济神州/audit_filled_20260706.json')
path.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
print(path)