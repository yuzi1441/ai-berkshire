import pandas as pd, re, json
for file in ['sources/sec/2025_10k.html','sources/sec/2026_q1_10q.html','sources/sec/2025_fy_press.html','sources/sec/2026_q1_press.html']:
 print('\n====',file)
 tables=pd.read_html(file)
 for i,t in enumerate(tables):
  text=' '.join(map(str,t.astype(str).values.flatten()))
  if any(k.lower() in text.lower() for k in ['BRUKINSA','TEVIMBRA','Product revenue','Total revenues','Cash, cash equivalents','Net cash provided by']):
   print('\n-- table',i,'shape',t.shape,'keys:', ','.join([k for k in ['BRUKINSA','TEVIMBRA','Product revenue','Total revenues','Cash, cash equivalents','Net cash provided by'] if k.lower() in text.lower()]))
   print(t.to_string(max_rows=35, max_cols=12))