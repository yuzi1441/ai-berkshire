import subprocess, pathlib, os, sys
json_text=pathlib.Path('reports/工商银行/audit_results_20260707.json').read_text(encoding='utf-8')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',json_text,'--report','reports/工商银行/工商银行投资研究报告-20260707.md','--output-json']
env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',env=env)
pathlib.Path('reports/工商银行/audit_verdict_20260707.json').write_text(p.stdout + ('\nSTDERR:\n'+p.stderr if p.stderr else ''),encoding='utf-8')
print('return',p.returncode)
print(p.stdout[:4000])
print(p.stderr[:1000])