import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('tools').resolve()))
import report_audit
results = json.loads(Path('reports/平高电气/_manual_audit_results.json').read_text(encoding='utf-8-sig'))
outcome = report_audit.render_verdict(results, report_name='reports/平高电气/平高电气-earnings-2026Q1.md')
Path('reports/平高电气/_manual_audit_verdict.json').write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding='utf-8')
raise SystemExit(0 if outcome['verdict']=='PASS' else 1)

