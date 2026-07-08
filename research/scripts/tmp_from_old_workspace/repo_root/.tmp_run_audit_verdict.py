import json, subprocess, sys
from pathlib import Path
results=Path('.tmp_uih_audit_results.json').read_text(encoding='utf-8-sig')
cmd=[sys.executable,'tools/report_audit.py','verdict','--results',results,'--report','reports/联影医疗/联影医疗-earnings-2025年报及2026Q1.md']
print(subprocess.run(cmd, cwd='.', text=True, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout)
