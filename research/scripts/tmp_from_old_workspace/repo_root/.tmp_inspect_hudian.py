import pandas as pd, os
for fn in ['data/hudian_profit_em.csv','data/hudian_balance_em.csv','data/hudian_cashflow_em.csv','data/hudian_indicator_sina.csv']:
 print('\n---',fn, os.path.exists(fn), os.path.getsize(fn) if os.path.exists(fn) else '')
 if os.path.exists(fn):
  df=pd.read_csv(fn)
  print(df.shape)
  print(df.columns[:20].tolist())
  cols=['REPORT_DATE','NOTICE_DATE','TOTAL_OPERATE_INCOME','OPERATE_INCOME','OPERATE_COST','RESEARCH_EXPENSE','SALE_EXPENSE','MANAGE_EXPENSE','FINANCE_EXPENSE','OPERATE_PROFIT','NETPROFIT','PARENT_NETPROFIT','BASIC_EPS','DEDUCT_PARENT_NETPROFIT','TOTAL_ASSETS','TOTAL_LIABILITIES','MONETARYFUNDS','TOTAL_EQUITY','NETCASH_OPERATE','NETCASH_INVEST','NETCASH_FINANCE']
  present=[c for c in cols if c in df.columns]
  print(df[present].head(8).to_string(index=False))
