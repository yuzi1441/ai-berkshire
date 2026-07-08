import json, subprocess, sys
results=[
  {"id":1,"label":"营业收入 · 2026Q1","reported_value":703.97,"unit":"亿元","fetched_value":703.97,"fetched_source":"中国神华2026Q1原文PDF page 1","fetched_value2":703.97,"fetched_source2":"新浪公告镜像/financial_rigor交叉验证"},
  {"id":4,"label":"经营现金流 · 2026Q1","reported_value":173.63,"unit":"亿元","fetched_value":173.63,"fetched_source":"中国神华2026Q1原文PDF page 1/page 16","fetched_value2":173.63,"fetched_source2":"新浪公告镜像/financial_rigor交叉验证"},
  {"id":12,"label":"营业收入 · 调整后 2026 目标","reported_value":3600.00,"unit":"亿元","fetched_value":3600.00,"fetched_source":"中国神华2026Q1原文PDF page 10 经调整2026经营目标","fetched_value2":3600.00,"fetched_source2":"本地抽取 sources/2026Q1.txt page 10"},
]
res=json.dumps(results,ensure_ascii=False)
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',res]
cp=subprocess.run(cmd,encoding='utf-8',text=True,capture_output=True)
print(cp.stdout)
if cp.stderr: print(cp.stderr,file=sys.stderr)
raise SystemExit(cp.returncode)
