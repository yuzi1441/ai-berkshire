from pathlib import Path
import re
for name in ['2025AR','2026Q1']:
 text=Path(f'sources/002028/text/{name}.txt').read_text(encoding='utf-8')
 for pat in ['利润分配预案','现金红利','每10股派','权益分派','分红']:
  print('\n',name,pat)
  for m in list(re.finditer(pat,text))[:5]:
   s=max(0,m.start()-500); e=min(len(text),m.start()+1000)
   print(text[s:e].replace('\n',' ')[:1500]); print('---')
