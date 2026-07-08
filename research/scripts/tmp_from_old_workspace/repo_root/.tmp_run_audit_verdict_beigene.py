import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from tools.report_audit import render_verdict
results=json.load(open(r"reports\百济神州\百济神州研究报告-20260706-audit-filled.json", encoding='utf-8'))
render_verdict(results, report_name='百济神州研究报告-20260706.md')