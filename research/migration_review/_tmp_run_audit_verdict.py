import json, io, contextlib
from pathlib import Path
from tools.report_audit import render_verdict
results = json.loads(Path('reports/长江电力/audit_results_长江电力研究报告-20260707.json').read_text(encoding='utf-8'))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    verdict = render_verdict(results, 'reports/长江电力/长江电力研究报告-20260707.md')
text = buf.getvalue()
Path('reports/长江电力/audit_verdict_长江电力研究报告-20260707.txt').write_text(text, encoding='utf-8')
Path('reports/长江电力/audit_verdict_长江电力研究报告-20260707.json').write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding='utf-8')
print(text)
print('JSON_VERDICT=', verdict.get('verdict'))
