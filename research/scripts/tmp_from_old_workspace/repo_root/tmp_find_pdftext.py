from pathlib import Path
import re
texts={p.name:p.read_text(encoding='utf-8',errors='ignore') for p in Path('data_sources').glob('*.txt')}
for name,text in texts.items():
 print('\n====',name)
 for term in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','总资产','归属于上市公司股东的所有者权益','营业总收入','货币资金','资产总计','负债合计']:
  idx=text.find(term)
  if idx!=-1:
   print('---',term,'at',idx)
   print(text[idx:idx+800].replace('\n',' | '))