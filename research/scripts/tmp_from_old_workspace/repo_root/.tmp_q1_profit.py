from pathlib import Path
text=Path('sources/mindray/mindray-2026-q1.txt').read_text(encoding='utf-8')
for term in ['归属于母公司所有者的净利润','净利润','扣除非经常性损益']:
 print('\n###',term)
 start=0
 for _ in range(5):
  idx=text.find(term,start)
  print(idx)
  if idx<0: break
  print(text[max(0,idx-500):idx+1000])
  start=idx+len(term)
