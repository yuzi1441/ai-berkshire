from pathlib import Path
import re
text=Path('2025AnnualReportA.txt').read_text(encoding='utf-8', errors='ignore')
for page in [15,16,18,19,45,46,48,49,62,63,78,79,83,84,85,86,87,124,125,126,127,128]:
 m=re.search(rf'--- PAGE {page} ---\n(.*?)(?=\n--- PAGE {page+1} ---|\Z)', text, re.S)
 if m:
  Path(f'_2025_page_{page}.txt').write_text(m.group(1),encoding='utf-8')
  print('wrote',page,len(m.group(1)))
