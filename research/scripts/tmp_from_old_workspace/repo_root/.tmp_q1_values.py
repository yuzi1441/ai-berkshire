import pandas as pd
prof=pd.read_csv('data/tmp_cypc_stock_profit_sheet_by_report_em.csv')
cf=pd.read_csv('data/tmp_cypc_stock_cash_flow_sheet_by_report_em.csv')
for df,name,cols in [(prof,'profit',['REPORT_DATE','TOTAL_OPERATE_INCOME','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','BASIC_EPS']),(cf,'cash',['REPORT_DATE','NETCASH_OPERATE','NETCASH_INVEST','NETCASH_FINANCE','CONSTRUCT_LONG_ASSET'])]:
 print('\n',name)
 print(df[['REPORT_DATE','REPORT_TYPE']+[c for c in cols if c not in ['REPORT_DATE'] and c in df.columns]].head(8).to_string(index=False))
