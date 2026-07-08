import pandas as pd, pathlib, json, math, re
src=pathlib.Path('reports/长江电力/sources')
profit=pd.read_csv(src/'ak_profit_em.csv')
bal=pd.read_csv(src/'ak_balance_em.csv')
cash=pd.read_csv(src/'ak_cash_em.csv')
ths=pd.read_csv(src/'ak_ths_abstract.csv')
for df in [profit,bal,cash]:
    df['date']=pd.to_datetime(df['REPORT_DATE']).dt.strftime('%Y-%m-%d')
    # sort desc already

dates=['2025-12-31','2024-12-31','2023-12-31','2022-12-31','2021-12-31','2026-03-31']
fields_profit=['TOTAL_OPERATE_INCOME','OPERATE_INCOME','OPERATE_COST','TOTAL_OPERATE_COST','OPERATE_PROFIT','TOTAL_PROFIT','NETPROFIT','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','BASIC_EPS','DILUTED_EPS']
fields_bal=['MONETARYFUNDS','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','PARENT_EQUITY','TOTAL_CURRENT_ASSETS','TOTAL_CURRENT_LIAB','SHORT_LOAN','NONCURRENT_LIAB_1YEAR','LONG_LOAN','BOND_PAYABLE','LEASE_LIAB','FIXED_ASSET','CIP']
fields_cash=['NETCASH_OPERATE','CONSTRUCT_LONG_ASSET','NETCASH_INVEST','NETCASH_FINANCE','ASSIGN_DIVIDEND_PORFIT','PAY_DEBT_CASH','RECEIVE_LOAN_CASH','ISSUE_BOND']
for name,df,fields in [('profit',profit,fields_profit),('balance',bal,fields_bal),('cash',cash,fields_cash)]:
 print('\n###',name)
 rows=[]
 for d in dates:
  row=df[df['date']==d]
  if row.empty: continue
  r=row.iloc[0]
  rec={'date':d,'report':r.get('REPORT_DATE_NAME')}
  for f in fields:
   if f in df.columns:
    rec[f]=r.get(f)
  rows.append(rec)
 out=pd.DataFrame(rows)
 print(out.to_string(index=False))
 out.to_csv(src/f'selected_{name}.csv',index=False,encoding='utf-8-sig')
print('\n### ths annual')
print(ths[ths['报告期'].isin(dates)].sort_values('报告期',ascending=False).to_string(index=False))
