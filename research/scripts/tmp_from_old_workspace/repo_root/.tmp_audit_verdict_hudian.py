import json, subprocess, os, pathlib
results=[
 {"id":4,"label":"归母净利润 2026Q1","reported_value":12.42,"unit":"亿元","fetched_value":12.42081367,"fetched_source":"巨潮资讯2026Q1报告","fetched_value2":12.42081367,"fetched_source2":"东方财富利润表接口"},
 {"id":5,"label":"扣非归母净利润 2025","reported_value":37.61,"unit":"亿元","fetched_value":37.60567906,"fetched_source":"巨潮资讯2025年报","fetched_value2":37.60567906,"fetched_source2":"东方财富利润表接口"},
 {"id":12,"label":"货币资金 2025","reported_value":25.79,"unit":"亿元","fetched_value":25.79107305,"fetched_source":"巨潮资讯2025年报资产负债表","fetched_value2":25.79107305,"fetched_source2":"东方财富资产负债表接口"},
 {"id":15,"label":"资产负债率 2026Q1","reported_value":48.64,"unit":"%","fetched_value":48.6431,"fetched_source":"巨潮资讯2026Q1资产负债表计算","fetched_value2":48.6431,"fetched_source2":"东方财富资产负债表接口计算"},
 {"id":14,"label":"资产负债率 2025","reported_value":46.46,"unit":"%","fetched_value":46.4574,"fetched_source":"巨潮资讯2025年报资产负债表计算","fetched_value2":46.4574,"fetched_source2":"东方财富资产负债表接口计算"},
 {"id":18,"label":"PCB合计毛利率","reported_value":36.91,"unit":"%","fetched_value":36.91,"fetched_source":"巨潮资讯2025年报主营构成","fetched_value2":36.9127,"fetched_source2":"东方财富主营构成接口"},
 {"id":29,"label":"工业控制及其他PCB占总收入","reported_value":2.34,"unit":"%","fetched_value":2.3355,"fetched_source":"巨潮资讯2025年报主营构成计算","fetched_value2":2.3355,"fetched_source2":"东方财富主营构成接口计算"},
 {"id":28,"label":"工业控制及其他PCB收入","reported_value":4.42,"unit":"亿元","fetched_value":4.42428873,"fetched_source":"巨潮资讯2025年报主营构成","fetched_value2":4.42428873,"fetched_source2":"东方财富主营构成接口"},
 {"id":30,"label":"工业控制及其他PCB毛利率","reported_value":42.10,"unit":"%","fetched_value":42.10,"fetched_source":"巨潮资讯2025年报主营构成","fetched_value2":42.10,"fetched_source2":"东方财富主营构成接口"},
 {"id":32,"label":"外销PCB收入","reported_value":155.43,"unit":"亿元","fetched_value":155.42868460,"fetched_source":"巨潮资讯2025年报主营构成","fetched_value2":155.42868460,"fetched_source2":"东方财富主营构成接口"},
 {"id":36,"label":"内销PCB收入","reported_value":26.00,"unit":"亿元","fetched_value":26.00439801,"fetched_source":"巨潮资讯2025年报主营构成","fetched_value2":26.00439801,"fetched_source2":"东方财富主营构成接口"},
 {"id":55,"label":"2025 PE","reported_value":64.86,"unit":"x","fetched_value":64.8602536871,"fetched_source":"financial_rigor.py verify-valuation","fetched_value2":64.86,"fetched_source2":"市值/2025归母净利润手工复算"},
 {"id":65,"label":"乐观三年后目标价","reported_value":174.60,"unit":"元","fetched_value":174.6,"fetched_source":"financial_rigor.py three-scenario","fetched_value2":174.6,"fetched_source2":"EPS*PE复算"},
 {"id":70,"label":"中性三年后目标价","reported_value":105.70,"unit":"元","fetched_value":105.7,"fetched_source":"financial_rigor.py three-scenario","fetched_value2":105.7,"fetched_source2":"EPS*PE复算"},
 {"id":74,"label":"悲观终值PE","reported_value":25.00,"unit":"x","fetched_value":25.00,"fetched_source":"financial_rigor.py three-scenario参数","fetched_value2":25.00,"fetched_source2":"报告估值假设"}
]
pathlib.Path('reports/沪电股份/report_audit_verdict_input_current.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
cmd=['python','tools/report_audit.py','verdict','--results',json.dumps(results,ensure_ascii=False)]
env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
p=subprocess.run(cmd,cwd='.',env=env,capture_output=True,text=True)
print(p.stdout)
print(p.stderr)
print('returncode',p.returncode)
pathlib.Path('reports/沪电股份/report_audit_verdict_current.txt').write_text(p.stdout+p.stderr+f'\nreturncode {p.returncode}\n',encoding='utf-8')
