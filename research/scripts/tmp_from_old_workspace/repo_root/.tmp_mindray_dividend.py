from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
for term in ['利润分配预案','现金分红政策','每10股','现金分红','回购']:
 print('\n###',term)
 start=0
 for k in range(2):
  idx=text.find(term,start)
  print(idx)
  if idx<0: break
  print(text[max(0,idx-600):idx+1600])
  start=idx+len(term)
