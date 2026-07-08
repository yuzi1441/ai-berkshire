import json, pathlib, subprocess, sys, os
# previous samples remain valid after wording fix; run verdict and avoid console encoding by writing files only
jsonstr=pathlib.Path('sources/audit_results.json').read_text(encoding='utf-8')
env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'
res=subprocess.run([sys.executable, '..\\..\\tools\\report_audit.py', 'verdict', '--results', jsonstr, '--report', '中国神华研究报告-20260707.md'], capture_output=True, text=True, encoding='utf-8', env=env)
pathlib.Path('sources/audit_verdict.txt').write_text((res.stdout or '') + ('\nSTDERR:\n'+res.stderr if res.stderr else ''), encoding='utf-8')
pathlib.Path('sources/audit_returncode.txt').write_text(str(res.returncode), encoding='utf-8')
