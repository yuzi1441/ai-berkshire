import pdfplumber, re
pdf='icbc_2026_q1_en.pdf'
with pdfplumber.open(pdf) as p:
 for i,page in enumerate(p.pages, start=1):
  txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
  if any(k in txt for k in ['Non-performing','Capital adequacy','Allowance to NPLs','net interest margin','Customer deposits','loan']):
   print('\n---PAGE',i,'---')
   print(txt[:4000])