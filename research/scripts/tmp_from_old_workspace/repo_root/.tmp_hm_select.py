import pandas as pd, json
for file in ['data/002270/profit_em_20260706.csv','data/002270/balance_em_20260706.csv','data/002270/cash_em_20260706.csv','data/002270/indicator_em_20260706.csv']:
 df=pd.read_csv(file)
 print('\n',file)
 cols=['REPORT_DATE','REPORT_DATE_NAME','REPORT_TYPE']
 for c in ['TOTAL_OPERATE_INCOME','OPERATE_INCOME','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','TOTAL_OPERATE_COST','OPERATE_COST','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_PARENT_EQUITY','NETCASH_OPERATE','CONSTRUCT_LONG_ASSET','FCFF_FORWARD','FCFF_BACK','XSMLL','XSJLL','ROEJQ','ZCFZL','EPSJB','BPS','TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR']:
  if c in df.columns: cols.append(c)
 print(df[cols].head(8).to_string(index=False))
