from pathlib import Path
import re
for txtp in ['sources/ICBC_2024_AnnualReport_EN.pdf.txt','sources/ICBC_2023_AnnualReport_EN.pdf.txt','sources/ICBC_2022_AnnualReport_EN.pdf.txt']:
    text=Path(txtp).read_text(encoding='utf-8', errors='ignore')
    print('\n########',txtp,'########')
    for page in range(12,20):
        m=re.search(rf'--- PAGE {page} ---\n(.*?)(?=\n--- PAGE {page+1} ---|\Z)', text, re.S)
        if m:
            print(f'\n===== PAGE {page} =====')
            print(m.group(1)[:4500])
