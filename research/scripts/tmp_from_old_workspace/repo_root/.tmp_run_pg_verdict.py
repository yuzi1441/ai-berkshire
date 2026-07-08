import json, subprocess, pathlib, sys
path=pathlib.Path('reports/平高电气/audit_results_20260707.json')
results=path.read_text(encoding='utf-8')
cmd=[sys.executable, 'tools/report_audit.py', 'verdict', '--results', results, '--report', 'reports/平高电气/平高电气研究报告-20260707.md']
cp=subprocess.run(cmd, cwd='.', text=True, capture_output=True, encoding='utf-8')
print(cp.stdout)
if cp.stderr:
    print('STDERR:', cp.stderr)
print('returncode', cp.returncode)
raise SystemExit(cp.returncode)
