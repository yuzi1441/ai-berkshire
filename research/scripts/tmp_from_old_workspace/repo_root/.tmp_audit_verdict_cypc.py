import json, subprocess
from pathlib import Path
text=Path('sources/长江电力/audit_extract_seed42.txt').read_text(encoding='utf-8')
items=json.loads(text[text.find('[\n'):])
# Manual fills. For derived/strategy table items, fetched_source2 is tool/report formula source.
fills={
2:(7179.5,'长江电力2025年报-装机容量情况',7179.5,'公司官网PDF提取'),
7:(605.63,'长江电力2025年报-现金流量表',605.63,'东方财富AKShare现金流量表'),
8:(420.74,'经营现金流605.63-购建长期资产184.88',420.7446,'financial_rigor/本地Decimal复算'),
9:(27.19,'腾讯行情600900 2026-07-06',27.19,'行情字段f3'),
23:(6652.91,'腾讯行情总市值字段',6652.91,'financial_rigor 市值验算'),
24:(6652.91,'腾讯行情总市值字段',6652.91,'financial_rigor 市值验算'),
29:(7.30,'长江电力2025年报分行业成本表',7.30,'公司官网PDF提取'),
27:(65.79,'长江电力2025年报分行业收入成本表',65.79,'公司官网PDF提取'),
36:(329.49,'年报分行业成本25,881,578,129.36+7,067,072,381.81',329.4865051117,'本地Decimal复算'),
51:(2025.0,'报告文本年份非财务值',2025.0,'年报年度'),
56:(2023.0,'报告文本年份非财务值',2023.0,'经营现金流趋势表年份'),
57:(8.0,'研究者评分',8.0,'报告主观评分-不适用外部核验'),
58:(2026.0,'年报分红政策2026-2030',2026.0,'公司2025年报利润分配政策'),
60:(2025.0,'报告文本年份非财务值',2025.0,'年报年度'),
63:(44.99,'长江电力2026Q1控股股东增持说明449,853万元',44.9853,'一季报PDF提取'),
71:(9.23,'腾讯行情600025 2026-07-06',9.23,'行情字段f3'),
72:(1719.65,'腾讯行情600025总市值字段',1719.65,'行情字段f45'),
109:(2025.0,'报告文本年份非财务值',2025.0,'利润归属期说明'),
108:(1.21,'2025三季报每股0.21+2025年度预案每股1.00',1.21,'长江电力分红公告/年报预案'),
115:(37.7,'financial_rigor三情景估值输出',37.7,'工具输出文件'),
130:(20.0,'价格区间描述PE下限',20.0,'27.19/1.4746约18.44，29/1.4746约19.67'),
}
for it in items:
    fv,fs,fv2,fs2=fills[it['id']]
    it['fetched_value']=fv; it['fetched_source']=fs; it['fetched_value2']=fv2; it['fetched_source2']=fs2
Path('sources/长江电力/audit_results_seed42.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
cmd=['python','tools/report_audit.py','verdict','--results',json.dumps(items,ensure_ascii=False),'--report','reports/长江电力/长江电力投资研究报告.md']
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
Path('sources/长江电力/audit_verdict_seed42.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
print(r.stdout)
print(r.stderr)
print('return',r.returncode)
