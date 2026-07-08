import pandas as pd
for fn in ['data/hudian_cashflow_em.csv','data/hudian_profit_em.csv','data/hudian_balance_em.csv']:
 df=pd.read_csv(fn)
 print('\n---',fn,'---')
 for c in df.columns:
  if any(k in c.upper() for k in ['CONSTRUCT','FIXED','CAPITAL','ASSET','CASH','PAY','PURCHASE','INVEST','TOTAL_OPERATE_INCOME','OPERATE_COST','OPERATE_PROFIT','PARENT_NETPROFIT','NETCASH_OPERATE']):
   print(c)
