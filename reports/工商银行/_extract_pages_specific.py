from pathlib import Path
import re
text=Path('2025AnnualReportA.txt').read_text(encoding='utf-8', errors='ignore')
for page in [101,113,114,115,116,117,118,119,120,121,45,46,48,49,62,63,78,79,83,84,85,86,87]:
    m=re.search(rf'--- PAGE {page} ---\n(.*?)(?=\n--- PAGE {page+1} ---|\Z)', text, re.S)
    if m:
        print(f'\n===== PAGE {page} =====')
        print(m.group(1)[:5000])
