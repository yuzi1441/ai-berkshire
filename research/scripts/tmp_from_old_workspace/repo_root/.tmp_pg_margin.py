import pdfplumber, pathlib, re
for year in [2025,2024,2023,2022,2021]:
 text='\n'.join((p.extract_text() or '') for p in pdfplumber.open(pathlib.Path(f'sources/pinggao/annual{year}.pdf')).pages)
 print('\n====',year,'====')
 for pat in ['营业收入','营业成本','毛利率','主营业务分行业','分行业','高压板块','输配电设备']:
  idx=text.find(pat)
  if idx!=-1:
   print('\n---',pat,'---')
   print(text[max(0,idx-200):idx+1000])
   break
 # find specific line 科目 table
 idx=text.find('利润表及现金流量表相关科目变动分析表')
 print('\n---analysis table---')
 print(text[idx:idx+1800] if idx!=-1 else 'not found')
