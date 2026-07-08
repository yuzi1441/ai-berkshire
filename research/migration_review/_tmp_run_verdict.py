import subprocess, pathlib, sys
json_text=pathlib.Path('reports/联影医疗/sources/audit_results.json').read_text(encoding='utf-8')
r=subprocess.run([sys.executable,'tools/report_audit.py','verdict','--results',json_text,'--report','reports/联影医疗/巴菲特Checklist-联影医疗.md'],capture_output=True,text=True,encoding='utf-8')
pathlib.Path('reports/联影医疗/sources/audit_verdict.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
print('returncode',r.returncode)
print(r.stdout)
print(r.stderr)
