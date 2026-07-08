import pandas as pd
bal=pd.read_csv('data/hengrui/balance_em.csv')
cols=list(bal.columns)
for pat in ['FVTPL','TRAD','SHORT','OTHER_CURRENT','OTHER_NONCURRENT','DEBT','PAYABLE','BORROW','LOAN','CURRENT_LIAB','NONCURRENT_LIAB','CONTRACT','PAYROLL','TAX','DIVIDEND']:
 print('\n',pat,[c for c in cols if pat in c.upper()][:50])
