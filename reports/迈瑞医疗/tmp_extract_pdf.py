import pdfplumber, pathlib, re
for pdf in ['source_pdfs/mindray_2025_annual.pdf','source_pdfs/mindray_2026_q1.pdf']:
 print('\nPDF',pdf)
 with pdfplumber.open(pdf) as p:
  print('pages',len(p.pages))
  text='\n'.join((page.extract_text() or '') for page in p.pages[:10])
  print(text[:5000])
  pathlib.Path(pdf+'.txt').write_text('\n'.join((page.extract_text() or '') for page in p.pages),encoding='utf-8')
