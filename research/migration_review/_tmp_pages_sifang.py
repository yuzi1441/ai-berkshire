from pathlib import Path
import pdfplumber, re, json
p=Path('data/raw/sifang/annual.pdf')
with pdfplumber.open(p) as pdf:
 for i in range(len(pdf.pages)):
  text=pdf.pages[i].extract_text() or ''
  if any(k in text for k in ['合并资产负债表','合并利润表','合并现金流量表','主要会计数据','主营业务分产品情况','前10名股东','利润分配预案']):
   print('\n--- PAGE',i+1,'---')
   print(text[:3500])