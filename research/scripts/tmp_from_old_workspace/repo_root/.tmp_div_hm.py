import pdfplumber, pathlib, re, pandas as pd, json
patterns=['现金分红','利润分配','回购','股份回购','派发现金红利','现金红利']
for fp in ['sources/002270/2025AR_1224986242.pdf','sources/002270/2024AR_1223055875.pdf','sources/002270/2023AR_1219567826.pdf']:
 print('\nFILE',fp)
 with pdfplumber.open(fp) as pdf:
  for i,p in enumerate(pdf.pages):
   txt=p.extract_text() or ''
   if any(k in txt for k in patterns):
    if '利润分配' in txt or '现金分红' in txt or '派发现金红利' in txt or '回购' in txt:
     print('--- page',i+1,'---')
     m=txt[:2500]
     print(m.replace('\uf052','').replace('\uf0a3','')[:2500])
     if i>80: break
