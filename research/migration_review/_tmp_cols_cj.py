import pandas as pd, pathlib
src=pathlib.Path('reports/长江电力/sources')
for f in src.glob('*.csv'):
 print('\n',f.name)
 df=pd.read_csv(f, nrows=1)
 print(list(df.columns)[:120])
