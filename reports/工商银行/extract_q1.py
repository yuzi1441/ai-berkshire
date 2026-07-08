import pdfplumber, pathlib
for fname in ['icbc_2026_q1_A.pdf']:
 pdf=pathlib.Path('_source')/fname
 with pdfplumber.open(pdf) as p:
  print(fname,'pages',len(p.pages))
  for pg in range(1,min(len(p.pages),20)+1):
   txt=p.pages[pg-1].extract_text() or ''
   if any(k in txt for k in ['主要财务数据','营业收入','净利润','资本充足率','不良贷款率','净利息差']):
    print('\n==== page',pg,'====')
    print(txt[:3000])
