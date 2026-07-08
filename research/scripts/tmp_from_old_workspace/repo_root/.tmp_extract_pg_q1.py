import pdfplumber, pathlib, re
for name in ['q1_2026','rights2025']:
 p=pathlib.Path(f'sources/pinggao/{name}.pdf')
 text='\n'.join((pg.extract_text() or '') for pg in pdfplumber.open(p).pages)
 pathlib.Path(f'sources/pinggao/{name}.txt').write_text(text,encoding='utf-8')
 print(name, len(text), text[:2000])
 for pat in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','总资产','股东信息','权益分派']:
  idx=text.find(pat)
  if idx!=-1: print('\n---',pat,'---\n',text[max(0,idx-200):idx+800])
