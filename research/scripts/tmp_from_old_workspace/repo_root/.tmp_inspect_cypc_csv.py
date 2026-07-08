import pandas as pd, glob, os
for f in glob.glob('data/tmp_cypc_*.csv'):
 print('\n###', f)
 df=pd.read_csv(f)
 print(df.shape)
 print(df.columns.tolist()[:30])
 print(df.head(5).to_string())
