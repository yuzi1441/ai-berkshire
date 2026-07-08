import json, subprocess, pathlib, os, sys
results=pathlib.Path('reports/东方电子/audit_results_20260707.json').read_text(encoding='utf-8')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',results,'--report','reports/东方电子/东方电子投资研究报告_20260707.md']
env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
res=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',env=env)
path=pathlib.Path('reports/东方电子/audit_verdict_20260707.txt')
path.write_text((res.stdout or '') + (('\nSTDERR:\n'+res.stderr) if res.stderr else ''),encoding='utf-8')
print('returncode',res.returncode)
print(res.stdout)
if res.stderr: print('STDERR',res.stderr)
