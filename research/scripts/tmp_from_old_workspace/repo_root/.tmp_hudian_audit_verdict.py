import json, subprocess, pathlib, os
results=[
  {"id":2,"label":"总股本 · 数值","reported_value":1924363537.0,"unit":"","fetched_value":1924363537.0,"fetched_source":"2025年报/腾讯行情","fetched_value2":1924363537.0,"fetched_source2":"腾讯行情字段"},
  {"id":3,"label":"总市值 · 数值","reported_value":2479.16,"unit":"亿元","fetched_value":2479.1575447171,"fetched_source":"financial_rigor: price*shares","fetched_value2":2479.16,"fetched_source2":"腾讯行情总市值"},
  {"id":4,"label":"2025A PE · 数值","reported_value":64.82,"unit":"x","fetched_value":64.819,"fetched_source":"financial_rigor: price/2025 EPS","fetched_value2":64.82,"fetched_source2":"2025 EPS复算"},
  {"id":15,"label":"数据通讯 · 同比 / 说明","reported_value":45.21,"unit":"%","fetched_value":45.21,"fetched_source":"2025年报分业务表","fetched_value2":45.21,"fetched_source2":"pdfplumber年报抽取"},
  {"id":14,"label":"数据通讯 · 毛利率","reported_value":39.68,"unit":"%","fetched_value":39.68,"fetched_source":"2025年报分业务表","fetched_value2":39.68,"fetched_source2":"pdfplumber年报抽取"},
  {"id":12,"label":"数据通讯 · 2025 收入","reported_value":146.56,"unit":"亿元","fetched_value":146.56300288,"fetched_source":"2025年报分业务表","fetched_value2":146.56,"fetched_source2":"年报金额14656300288元四舍五入"},
  {"id":18,"label":"智能汽车 · 毛利率","reported_value":22.84,"unit":"%","fetched_value":22.84,"fetched_source":"2025年报分业务表","fetched_value2":22.84,"fetched_source2":"pdfplumber年报抽取"},
  {"id":55,"label":"悲观 · 目标 PE","reported_value":22.0,"unit":"x","fetched_value":22.0,"fetched_source":"报告情景假设","fetched_value2":22.0,"fetched_source2":"financial_rigor three-scenario输入"}
]
path=pathlib.Path('reports/沪电股份/沪电股份-audit-results-20260706.json')
path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
res=subprocess.run(['python','tools/report_audit.py','verdict','--results',json.dumps(results,ensure_ascii=False)],cwd=pathlib.Path.cwd(),env={**os.environ,'PYTHONIOENCODING':'utf-8'},text=True,capture_output=True,encoding='utf-8')
print(res.stdout)
if res.stderr: print('STDERR',res.stderr)
(pathlib.Path('reports/沪电股份/沪电股份-audit-verdict-20260706.txt')).write_text(res.stdout+('\nSTDERR\n'+res.stderr if res.stderr else ''),encoding='utf-8')
print('json',path.resolve())
print('verdict',(pathlib.Path('reports/沪电股份/沪电股份-audit-verdict-20260706.txt')).resolve())
