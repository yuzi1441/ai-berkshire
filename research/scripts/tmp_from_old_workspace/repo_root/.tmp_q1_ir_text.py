import pdfplumber
for fn in ['2026Q1.pdf','IR20260706.pdf']:
 print('\n###',fn)
 with pdfplumber.open('sources/沪电股份/'+fn) as pdf:
  for i,p in enumerate(pdf.pages):
   text=p.extract_text() or ''
   print('\n--- PAGE',i+1,'---')
   print(text[:2500].replace('\n',' | '))
