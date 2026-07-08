import re, json
from pathlib import Path
html=Path('sources/sec/2025_10k.html').read_text(encoding='utf-8',errors='ignore')
for term in ['BRUKINSAMember','TislelizumabMember','XGEVAMember']:
 print('\nTERM',term)
 for m in re.finditer(term, html):
  print('pos',m.start())
  print(html[max(0,m.start()-1200):m.start()+2200])
  break
PY