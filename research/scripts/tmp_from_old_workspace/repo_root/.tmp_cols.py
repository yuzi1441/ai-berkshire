import pandas as pd, re
base='data/hengrui'
for name in ['profit_em','balance_em','cash_em']:
 df=pd.read_csv(f'{base}/{name}.csv')
 print('\n###', name, df.shape)
 cols=list(df.columns)
 for pat in ['TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','PARENT','EQUITY','MONETARY','OPERATE','NETCASH','CAPITAL','CONSTRUCT','FIXED','INVENTORY','ACCOUNTS_RECE','TOTAL_SHARE','SHARE','CASH','LIABIL','ASSET','GOODWILL','INTANGIBLE']:
  hits=[c for c in cols if pat in c.upper()]
  if hits: print(pat, hits[:30])
