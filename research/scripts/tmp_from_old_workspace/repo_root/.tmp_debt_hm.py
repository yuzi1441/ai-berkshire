import pandas as pd, json
bal=pd.read_csv('data/002270/balance_em_20260706.csv')
row=bal.iloc[0]
for c in ['MONETARYFUNDS','MONETARY_FUND','CURRENCY_FUNDS','CASH_DEPOSIT_CENTRAL_BANK','TRADE_FINASSET','FVTPL_FINASSET','SHORT_LOAN','SHORT_BORROW','SHORT_FIN_PAYABLE','NONCURRENT_LIAB_1YEAR','LEASE_LIAB','LONG_LOAN','LONG_PAYABLE','BOND_PAYABLE','TOTAL_LIABILITIES','TOTAL_ASSETS','TOTAL_PARENT_EQUITY','TOTAL_CURRENT_LIAB','TOTAL_NONCURRENT_LIAB']:
    if c in bal.columns:
        print(c, row[c])
# print all non-null columns with cash/debt-like names in latest row
for c in bal.columns:
    v=row[c]
    if pd.notna(v) and any(k in c.upper() for k in ['MONEY','MONET','CASH','LOAN','BORROW','SHORT','BOND','LEASE','PAYABLE','DEBT','FUND']):
        print('MATCH',c,v)
