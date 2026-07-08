from pathlib import Path
import re
text=Path('sources/ICBC_2024_AnnualReport_EN.pdf.txt').read_text(encoding='utf-8', errors='ignore')
for page in range(14,20):
    m=re.search(rf'--- PAGE {page} ---\n(.*?)(?=\n--- PAGE {page+1} ---|\Z)', text, re.S)
    if m:
        print(f'\n===== PAGE {page} =====')
        print(m.group(1)[:7000])
