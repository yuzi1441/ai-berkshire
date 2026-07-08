import subprocess, pathlib, sys
repo=pathlib.Path.cwd()
json_text=(repo/'reports/中国神华/audit_results_20260706.json').read_text(encoding='utf-8')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',json_text,'--report','reports/中国神华/中国神华研究报告-20260706.md','--output-json']
res=subprocess.run(cmd,cwd=repo,text=True,capture_output=True,encoding='utf-8')
print('returncode',res.returncode)
if res.stderr: print('STDERR:',res.stderr)
print(res.stdout)
(repo/'reports/中国神华/audit_verdict_20260706.json').write_text(res.stdout,encoding='utf-8')
if res.returncode: raise SystemExit(res.returncode)
