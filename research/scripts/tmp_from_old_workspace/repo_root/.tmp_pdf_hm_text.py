import pdfplumber, re, os, json
files=['sources/002270/2025AR_1224986242.pdf','sources/002270/2026Q1_1225181771.pdf','sources/002270/2024AR_1223055875.pdf']
for fp in files:
 print('\nFILE',fp)
 with pdfplumber.open(fp) as pdf:
  print('pages', len(pdf.pages))
  for i,p in enumerate(pdf.pages[:12]):
   txt=p.extract_text() or ''
   if any(k in txt for k in ['主要会计数据','归属于上市公司股东','营业收入','现金流量净额','基本每股收益']):
    print('--- page',i+1,'---')
    print(txt[:2500])
