from pathlib import Path
import re
text=Path('sources/sec/2025_10k.html.txt').read_text(encoding='utf-8')
patterns=['Product revenues by product','BRUKINSA','TEVIMBRA','Collaboration','Revenue by geographic','United States','China','Europe','Net product revenue']
for pat in patterns:
 print('\n==',pat)
 found=0
 for m in re.finditer(re.escape(pat), text, re.I):
  print('pos',m.start()); print(text[max(0,m.start()-600):m.start()+1800]); found+=1
  if found>=3: break