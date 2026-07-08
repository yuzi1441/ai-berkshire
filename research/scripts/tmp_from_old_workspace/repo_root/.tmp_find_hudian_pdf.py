import pdfplumber,re
from pathlib import Path
path=Path('sources/沪电股份/2025AR.pdf')
patterns=['主要会计数据','营业收入','企业通讯市场板','汽车板','货币资金','经营活动产生的现金流量净额','购建固定资产','总股本','前十名股东','董事长','管理层讨论']
with pdfplumber.open(path) as pdf:
 for pat in patterns:
  print('\n###',pat)
  count=0
  for i,p in enumerate(pdf.pages):
   text=p.extract_text() or ''
   if pat in text:
    print('PAGE',i+1, text[:1600].replace('\n',' | '))
    count+=1
    if count>=3: break
