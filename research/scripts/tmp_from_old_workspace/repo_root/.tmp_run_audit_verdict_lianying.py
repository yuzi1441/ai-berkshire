import subprocess, pathlib, sys
results=pathlib.Path('reports/联影医疗/audit_results_20260706.json').read_text(encoding='utf-8')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',results,'--report','reports/联影医疗/联影医疗研究报告-20260706.md']
p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
path=pathlib.Path('reports/联影医疗/audit_verdict_20260706.txt')
path.write_text((p.stdout or '')+(p.stderr or ''),encoding='utf-8')
print(path.read_text(encoding='utf-8'))
raise SystemExit(p.returncode)
