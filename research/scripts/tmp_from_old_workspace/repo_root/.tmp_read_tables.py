import pandas as pd
from pathlib import Path
for file in ['sources/sec/2025_10k.html','sources/sec/2026_q1_10q.html','sources/sec/2025_fy_press.html','sources/sec/2026_q1_press.html']:
 print('\n====',file)
 try:
  tables=pd.read_html(file)
  print('tables',len(tables))
  for i,t in enumerate(tables):
   s=' '.join(map(str,t.astype(str).values.flatten()[:60]))
   if any(k.lower() in s.lower() for k in ['BRUKINSA','TEVIMBRA','Product revenue','Total revenues','cash, cash equivalents','Research and development']):
    print('\n-- table',i,'shape',t.shape)
    print(t.head(20).to_string())
 except Exception as e: print('ERR',e)