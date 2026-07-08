from pathlib import Path
import pdfplumber
for fn in ['2025_annual_sse_real.pdf','2026_q1_sse_real.pdf']:
 p=Path('sources/sifang')/fn
 txtp=p.with_suffix('.txt')
 texts=[]
 with pdfplumber.open(p) as pdf:
  print(fn,'pages',len(pdf.pages))
  for i,page in enumerate(pdf.pages):
   t=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
   texts.append(f'\n\n---PAGE {i+1}---\n'+t)
 txtp.write_text('\n'.join(texts),encoding='utf-8')
 print(txtp, txtp.stat().st_size)
