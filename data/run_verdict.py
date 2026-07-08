import subprocess, json, os, sys
results=[
 {"id":18,"label":"TAO CAI期初间接持股","reported_value":1561677,"unit":"股","fetched_value":1561677,"fetched_source":"2025年报P129","fetched_value2":1561677,"fetched_source2":"本地pdfplumber抽取"},
 {"id":32,"label":"2025海外收入同比","reported_value":51.39,"unit":"%","fetched_value":51.39,"fetched_source":"2026年4月投资者关系活动记录","fetched_value2":51.39,"fetched_source2":"2025年报经营讨论"},
 {"id":87,"label":"2026Q1归母净利润","reported_value":3.99,"unit":"亿元","fetched_value":3.9886928278,"fetched_source":"2026Q1报告","fetched_value2":3.99,"fetched_source2":"financial_rigor calc"},
 {"id":95,"label":"关键管理人员报酬占净利润","reported_value":1.52,"unit":"%","fetched_value":1.5164,"fetched_source":"2025年报P369+financial_rigor","fetched_value2":1.52,"fetched_source2":"报告计算复核"},
 {"id":97,"label":"采购接受劳务关联交易占收入","reported_value":2.86,"unit":"%","fetched_value":2.8614,"fetched_source":"2025年报P365-366+financial_rigor","fetched_value2":2.86,"fetched_source2":"报告计算复核"}
]
env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
cp=subprocess.run([sys.executable,'tools/report_audit.py','verdict','--results',json.dumps(results,ensure_ascii=False)], cwd=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire', text=True, capture_output=True, env=env, encoding='utf-8', errors='replace')
print(cp.stdout)
print(cp.stderr,file=sys.stderr)
sys.exit(cp.returncode)
