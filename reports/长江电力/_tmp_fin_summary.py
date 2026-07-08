import pandas as pd
from pathlib import Path
inc=pd.read_csv('sources/eastmoney_income.csv')
bal=pd.read_csv('sources/ak_balance_em.csv')
cash=pd.read_csv('sources/ak_cash_em.csv')
# annual rows 2021-2025 and q1 2026
rows=[]
for date in ['2021-12-31 00:00:00','2022-12-31 00:00:00','2023-12-31 00:00:00','2024-12-31 00:00:00','2025-12-31 00:00:00','2026-03-31 00:00:00']:
    r=inc[inc['REPORT_DATE']==date].iloc[0]
    c=cash[cash['REPORT_DATE']==date].iloc[0]
    b=bal[bal['REPORT_DATE']==date].iloc[0]
    rows.append({
        'period':r['REPORT_DATE_NAME'],
        'revenue_亿元':round(r['OPERATE_INCOME']/1e8,2),
        'parent_np_亿元':round(r['PARENT_NETPROFIT']/1e8,2),
        'op_cf_亿元':round(c.get('NETCASH_OPERATE',float('nan'))/1e8,2),
        'assets_亿元':round(b['TOTAL_ASSETS']/1e8,2),
        'liab_ratio_%':round(b['TOTAL_LIABILITIES']/b['TOTAL_ASSETS']*100,2),
        'eps':r.get('BASIC_EPS')
    })
print(pd.DataFrame(rows).to_markdown(index=False))
# dividend csv
try:
    div=pd.read_csv('sources/ak_dividend.csv')
    print('\nDIV')
    print(div.head(20).to_string())
except Exception as e: print('div err',e)