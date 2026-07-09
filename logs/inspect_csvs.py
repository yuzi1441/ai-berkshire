import pandas as pd, pathlib
for name in ['abstract','sina']:
 p=f'data/600372/{name}.csv'
 print('\n',p)
 if pathlib.Path(p).exists():
  df=pd.read_csv(p)
  print(df.columns.tolist()[:30])
  print(df.shape)
  print(df.head(10).to_string())