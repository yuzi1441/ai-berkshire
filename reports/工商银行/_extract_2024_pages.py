from pathlib import Path
import re
text=Path('sources/ICBC_2024_AnnualReport_EN.pdf.txt').read_text(encoding='utf-8', errors='ignore')
for page in [15,16,17,18,19]:
    m=re.search(rf'--- PAGE {page} ---\n(.*?)(?=\n--- PAGE {page+1} ---|\Z)', text, re.S)
    if m:
        Path(f'_2024_page_{page}.txt').write_text(m.group(1),encoding='utf-8')
        print('wrote',page,len(m.group(1)))
