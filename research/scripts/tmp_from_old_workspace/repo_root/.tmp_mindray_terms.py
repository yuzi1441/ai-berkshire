from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
for term in ['股东信息','股东总数','持股情况','Smartco','Magnifice','Ever Union','珠海睿隆','李西廷']:
 print('\n###',term)
 start=0
 for k in range(3):
  idx=text.find(term,start)
  print(idx)
  if idx<0: break
  print(text[max(0,idx-400):idx+1800])
  start=idx+len(term)
