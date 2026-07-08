import pandas as pd, pathlib
base=pathlib.Path('reports/华明装备/sources/eastmoney')
for fn in ['profit_em.csv','cashflow_em.csv','balance_em.csv','financial_indicator.csv','financial_abstract.csv']:
 print('\n---',fn,'---')
 df=pd.read_csv(base/fn)
 print(df.shape)
 print(df.columns[:60].tolist())
 print(df.head(3).to_string())
