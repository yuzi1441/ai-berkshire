import pandas as pd
bal=pd.read_csv('data/lianying_balance.csv')
cols=['REPORT_DATE_NAME','MONETARYFUNDS','TRADE_FINASSET','SHORT_LOAN','LONG_LOAN','TOTAL_LIABILITIES','TOTAL_EQUITY','TOTAL_ASSETS','ACCOUNTS_RECE','INVENTORY','CONTRACT_LIAB','TOTAL_PARENT_EQUITY']
print(bal[[c for c in cols if c in bal.columns]].head(6).to_string(index=False))
