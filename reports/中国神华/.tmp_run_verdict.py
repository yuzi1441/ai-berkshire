import json, pathlib, subprocess, sys, os
jsonstr=pathlib.Path('sources/audit_results.json').read_text(encoding='utf-8')
env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
res=subprocess.run([sys.executable, '..\\..\\tools\\report_audit.py', 'verdict', '--results', jsonstr, '--report', '中国神华研究报告-20260707.md'], capture_output=True, text=True, encoding='utf-8', env=env)
pathlib.Path('sources/audit_verdict.txt').write_text((res.stdout or '') + ('\nSTDERR:\n'+res.stderr if res.stderr else ''), encoding='utf-8')
print('returncode', res.returncode)
print(res.stdout)
print(res.stderr)
sys.exit(res.returncode)
