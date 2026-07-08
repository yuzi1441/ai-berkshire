import pandas as pd
for file in ['data/002270/indicator_em_20260706.csv']:
 df=pd.read_csv(file)
 years=['2025年报','2024年报','2023年报','2022年报','2021年报']
 cols=['REPORT_DATE_NAME','TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR','XSMLL','XSJLL','ROEJQ','ZCFZL','EPSJB','BPS','FCFF_FORWARD','FCFF_BACK']
 print(df[df.REPORT_DATE_NAME.isin(years)][cols].to_string(index=False))
for file in ['data/002270/cash_em_20260706.csv']:
 df=pd.read_csv(file); print(df[df.REPORT_DATE_NAME.isin(years)][['REPORT_DATE_NAME','NETCASH_OPERATE','CONSTRUCT_LONG_ASSET']].to_string(index=False))
