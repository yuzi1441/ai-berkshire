from pypdf import PdfReader
from pathlib import Path
import re, json
patterns=['主要会计数据和财务指标','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','总资产','归属于上市公司股东的净资产','流动资产合计','资产总计','负债合计','股本','货币资金']
for p in [Path('sources/hengrui/2025AR_1225032585.pdf'), Path('sources/hengrui/2026Q1_1225145521.pdf')]:
 print('\n###',p.name)
 reader=PdfReader(str(p))
 for i,page in enumerate(reader.pages):
  text=page.extract_text() or ''
  if any(pt in text for pt in patterns[:6]):
   print('page',i+1,text[:2500].replace('\n',' | '))
   if i>20 and p.name.startswith('2025'): break
