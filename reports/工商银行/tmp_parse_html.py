from pathlib import Path
html=Path('icbc_download.html').read_text(encoding='utf-8', errors='ignore')
for s in ['2025','年度报告','第一季度','Announce20260429_5','2026']:
 print('TERM',s, html.find(s))
import re
for m in re.finditer(r'''https?://[^"']+\.pdf|[^"']+\.pdf''', html, re.I):
 print(m.group(0)[:200])