import pdfplumber, re, json
pdf='icbc_2025_annual_en.pdf'
terms=['Financial Highlights','net interest margin','Net interest margin','Return on average total assets','Return on weighted average equity','non-performing loan','NPL ratio','allowance to NPL','Capital adequacy ratio','Dividend','cash dividends','Loans and advances','Due to customers','Allowance to NPLs','Impairment losses']
with pdfplumber.open(pdf) as p:
 print('pages',len(p.pages))
 hits=[]
 for i,page in enumerate(p.pages, start=1):
  txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
  low=txt.lower()
  found=[t for t in terms if t.lower() in low]
  if found:
   hits.append((i,found,txt[:700].replace('\n',' | ')))
 for h in hits[:120]:
  print(h[0], h[1], h[2])