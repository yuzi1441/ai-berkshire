import pdfplumber, re, json
from pathlib import Path
items=[]
with pdfplumber.open('sources/沪电股份/2025AR.pdf') as pdf:
 for i,p in enumerate(pdf.pages):
  text=p.extract_text() or ''
  for pat in ['按行业分类','按产品分类','企业通讯市场板','汽车板','主营业务构成','营业收入构成','分行业','分产品','毛利率']:
   if pat in text:
    print('\nPAGE',i+1,'PAT',pat)
    print(text[:3000].replace('\n',' | '))
    break
