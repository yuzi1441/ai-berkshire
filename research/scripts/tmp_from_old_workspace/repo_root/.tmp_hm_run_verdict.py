import subprocess, pathlib, sys
json_text=pathlib.Path('reports/华明装备/sources/audit_results.json').read_text(encoding='utf-8')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',json_text,'--report','华明装备投资研究报告-20260706.md']
r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
path=pathlib.Path('reports/华明装备/sources/audit_verdict.txt')
path.write_text(r.stdout + ('\nSTDERR:\n'+r.stderr if r.stderr else ''),encoding='utf-8')
print('returncode',r.returncode)
print(path.read_text(encoding='utf-8'))
