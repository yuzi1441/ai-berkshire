import subprocess, pathlib, sys
j=pathlib.Path('reports/百济神州/audit_filled_20260706.json').read_text(encoding='utf-8')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',j,'--report','reports/百济神州/百济神州研究报告-20260706.md']
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
print(r.stdout)
print(r.stderr)
pathlib.Path('reports/百济神州/audit_verdict_20260706.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
sys.exit(r.returncode)