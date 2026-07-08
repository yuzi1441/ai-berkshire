from pathlib import Path
import subprocess, sys
results = Path('reports/四方股份/audit_results_20260707.json').read_text(encoding='utf-8')
out = Path('reports/四方股份/audit_verdict_20260707.txt')
cmd = [sys.executable, 'tools/report_audit.py', 'verdict', '--results', results, '--report', 'reports/四方股份/四方股份投资研究报告_20260707.md']
cp = subprocess.run(cmd, cwd='.', text=True, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out.write_text(cp.stdout, encoding='utf-8')
print(cp.stdout)
raise SystemExit(cp.returncode)