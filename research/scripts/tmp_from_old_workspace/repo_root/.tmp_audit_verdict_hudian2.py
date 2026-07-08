import json, subprocess, os, pathlib
results=json.loads(pathlib.Path('reports/沪电股份/report_audit_verdict_input_current.json').read_text(encoding='utf-8'))
cmd=['python','tools/report_audit.py','verdict','--results',json.dumps(results,ensure_ascii=False)]
env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
p=subprocess.run(cmd,cwd='.',env=env,capture_output=True)
out=p.stdout.decode('utf-8','replace')+p.stderr.decode('utf-8','replace')+f'\nreturncode {p.returncode}\n'
print(out)
pathlib.Path('reports/沪电股份/report_audit_verdict_current.txt').write_text(out,encoding='utf-8')
