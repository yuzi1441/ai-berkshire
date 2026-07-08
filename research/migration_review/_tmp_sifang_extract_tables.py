from pathlib import Path
import pdfplumber, re, json
p=Path('sources/sifang/2025_annual_sse_real.pdf')
with pdfplumber.open(p) as pdf:
 for page_no in [8,9,10,19,20,21,22,23,24,25,31,32,33,34,35,36,37,38,39,40,41,42,43,44,182,183,184,185,186,187,188,189,190,191,192,193,194,195]:
  if page_no>len(pdf.pages): continue
  page=pdf.pages[page_no-1]
  text=page.extract_text() or ''
  if any(k in text for k in ['主要会计数据','分季度','营业收入和营业成本','分行业','分产品','前五名客户','前五名供应商','现金流量表','合并资产负债表','利润表','研发投入','主营业务']):
   print('\n===== PAGE',page_no,'TEXT =====')
   print(text[:3500])
   tables=page.extract_tables()
   print('tables',len(tables))
   for ti,t in enumerate(tables[:3]):
    print('---table',ti,'rows',len(t),'---')
    for row in t[:12]: print(row)
q=Path('sources/sifang/2026_q1_sse_real.pdf')
with pdfplumber.open(q) as pdf:
 for page_no in range(1,min(10,len(pdf.pages))+1):
  page=pdf.pages[page_no-1]
  print('\n===== Q1 PAGE',page_no,'TEXT =====')
  print((page.extract_text() or '')[:2500])
  tables=page.extract_tables()
  print('tables',len(tables))
  for ti,t in enumerate(tables[:2]):
   print('---table',ti,'rows',len(t),'---')
   for row in t[:10]: print(row)
