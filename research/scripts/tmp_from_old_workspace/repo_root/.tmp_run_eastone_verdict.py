import json, pathlib, sys
sys.path.insert(0, 'tools')
import report_audit
results=json.loads(pathlib.Path('reports/东方电子/东方电子投资研究报告-20260707-audit-results.json').read_text(encoding='utf-8'))
outcome=report_audit.render_verdict(results, report_name='reports/东方电子/东方电子投资研究报告-20260707.md')
pathlib.Path('reports/东方电子/东方电子投资研究报告-20260707-audit-outcome.json').write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding='utf-8')
