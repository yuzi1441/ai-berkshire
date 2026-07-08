import pdfplumber, re
pdf='icbc_2025_annual_en.pdf'
need=['Asset quality','Five-category','overdue','real estate','Liquidity Risk','Market Risk','Interest Rate Risk','non-performing loans', 'Credit Risk']
with pdfplumber.open(pdf) as p:
 for i,page in enumerate(p.pages, start=1):
  txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
  if any(n.lower() in txt.lower() for n in need):
   if 30<=i<=90 or 150<=i<=230:
    print('\n---PAGE',i,'---')
    print(txt[:3500])