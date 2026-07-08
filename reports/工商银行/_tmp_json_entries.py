import re,json
from pathlib import Path
text=Path('_icbc_finreports.html').read_text(encoding='utf-8')
for m in re.finditer(r'\{[^{}]*?(?:2025AnnualReport|FirstQuarterlyReportof2026)[^{}]*?\}', text):
 print(m.group(0))