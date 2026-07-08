import pandas as pd, numpy as np, json, math
base='data/hengrui'
ind=pd.read_csv(f'{base}/indicator_em.csv')
pro=pd.read_csv(f'{base}/profit_em.csv')
bal=pd.read_csv(f'{base}/balance_em.csv')
cas=pd.read_csv(f'{base}/cash_em.csv')
periods=['2021年报','2022年报','2023年报','2024年报','2025年报','2026一季报']
cols_ind=['REPORT_DATE_NAME','TOTALOPERATEREVE','MLR','PARENTNETPROFIT','KCFJCXSYJLR','ROEJQ','ROEKCJQ','ZZCJLL','XSJLL','XSMLL','ZCFZL','BPS','EPSJB','MGJYXJJE','TOTAL_ROI','NET_ROI','LIABILITY']
print('IND')
print(ind[ind.REPORT_DATE_NAME.isin(periods)][cols_ind].to_string(index=False))
cols_pro=['REPORT_DATE_NAME','TOTAL_OPERATE_INCOME','OPERATE_INCOME','OPERATE_COST','OPERATE_PROFIT','TOTAL_PROFIT','NETPROFIT','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','BASIC_EPS','DILUTED_EPS','RD_EXPENSE','SALE_EXPENSE','MANAGE_EXPENSE','FINANCE_EXPENSE']
print('\nPRO')
print(pro[pro.REPORT_DATE_NAME.isin(periods)][[c for c in cols_pro if c in pro.columns]].to_string(index=False))
cols_bal=['REPORT_DATE_NAME','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','TOTAL_PARENT_EQUITY','MONETARYFUNDS','FVTPL_FINASSET','TRADING_FINASSET','OTHER_CURRENT_ASSET','FIXED_ASSET','INTANGIBLE_ASSET','GOODWILL','INVENTORY','ACCOUNTS_RECE','NOTE_ACCOUNTS_RECE','SHARE_CAPITAL','CAPITAL_RESERVE','SURPLUS_RESERVE','UNASSIGN_RPOFIT','SHORT_LOAN','NONCURRENT_LIAB_1YEAR','LONG_LOAN','BOND_PAYABLE','LEASE_LIAB','TOTAL_CURRENT_LIAB','TOTAL_CURRENT_ASSETS']
print('\nBAL cols exist')
print([c for c in cols_bal if c in bal.columns])
print(bal[bal.REPORT_DATE_NAME.isin(periods)][[c for c in cols_bal if c in bal.columns]].to_string(index=False))
cols_cash=['REPORT_DATE_NAME','NETCASH_OPERATE','CONSTRUCT_LONG_ASSET','DISPOSAL_LONG_ASSET','NETCASH_INVEST','NETCASH_FINANCE','END_CASH','BEGIN_CASH','CASH_EQUIVALENTS_INCREASE','PAY_CASH_DIVIDEND','BUY_SUBSIDIARY_EQUITY']
print('\nCASH')
print(cas[cas.REPORT_DATE_NAME.isin(periods)][[c for c in cols_cash if c in cas.columns]].to_string(index=False))
