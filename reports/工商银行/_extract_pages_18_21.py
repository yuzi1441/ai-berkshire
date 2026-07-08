from pathlib import Path
import re
p=Path('2025AnnualReportA.txt')
txt=p.read_text(encoding='utf-8', errors='ignore')
for page in range(17,22):
    m=re.search(rf'--- PAGE {page} ---\n(.*?)(?=\n--- PAGE {page+1} ---|\Z)', txt, re.S)
    if m:
        print(f'\n===== PAGE {page} =====')
        print(m.group(1)[:6000])
