import pdfplumber, re, pathlib, sys
for pdf in ['icbc_2026_q1_en.pdf','icbc_2025_annual_en.pdf']:
 print('\nPDF',pdf)
 with pdfplumber.open(pdf) as p:
  print('pages',len(p.pages))
  for i,page in enumerate(p.pages[:10], start=1):
   txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
   print('\n---PAGE',i,'---')
   print(txt[:3000])