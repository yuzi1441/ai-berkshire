import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path('tools').resolve()))
import report_audit
results=json.loads(Path('audit_results_icbc.json').read_text(encoding='utf-8-sig'))
report_audit.render_verdict(results, 'reports/工商银行/工商银行投资研究报告_20260707.md')

