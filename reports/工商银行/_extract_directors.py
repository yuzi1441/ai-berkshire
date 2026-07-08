from pathlib import Path
import re
p=Path('2025AnnualReportA.txt')
txt=p.read_text(encoding='utf-8', errors='ignore')
for page in range(113,123):
    m=re.search(rf'--- PAGE {page} ---\n(.*?)(?=\n--- PAGE {page+1} ---|\Z)', txt, re.S)
    if m:
        print(f'\n===== PAGE {page} =====')
        s=m.group(1)
        for term in ['廖林','刘珺','董事长','行长','任职','委任','2024','2025']:
            if term in s: pass
        print(s[:6000])
