from decimal import Decimal, getcontext
getcontext().prec=28
# values in CNY and shares
price=Decimal('27.19')
shares=Decimal('24468217716')
market_cap=price*shares
print('market_cap_yi', market_cap/Decimal('1e8'))
# EPS TTM from EPS
print('eps_ttm', Decimal('1.4101')-Decimal('0.2117')+Decimal('0.2763'))
print('pe_ttm', price/(Decimal('1.4101')-Decimal('0.2117')+Decimal('0.2763')))
print('pe_2025', price/Decimal('1.4101'))
print('pb_2026q1', price/Decimal('9.31'))
print('div_yield_1.0', Decimal('1.00')/price*100)
print('div_yield_0.79', Decimal('0.79')/price*100)
# FCF
cfo2025=Decimal('60562925570.41'); capex2025=Decimal('18488466859.29')
fcf2025=cfo2025-capex2025
print('fcf2025_yi',fcf2025/Decimal('1e8'), 'fcf_yield', fcf2025/market_cap*100, 'pfcf', market_cap/fcf2025, 'fcf_ps', fcf2025/shares)
# TTM fcf simple: 2025 + q1 2026 - q1 2025; q1 cfo/capex from statement? Q1 2026 capex extracted 3.220191e9; 2025 q1 need from report? use Ak cash date 2025-03-31
import pandas as pd, pathlib
cash=pd.read_csv('reports/长江电力/sources/ak_cash_em.csv')
cash['date']=pd.to_datetime(cash['REPORT_DATE']).dt.strftime('%Y-%m-%d')
for d in ['2025-03-31','2026-03-31']:
 r=cash[cash.date==d].iloc[0]
 print(d, r.NETCASH_OPERATE, r.CONSTRUCT_LONG_ASSET, (Decimal(str(r.NETCASH_OPERATE))-Decimal(str(r.CONSTRUCT_LONG_ASSET)))/Decimal('1e8'))
r25q1=cash[cash.date=='2025-03-31'].iloc[0]
r26q1=cash[cash.date=='2026-03-31'].iloc[0]
fcfttm=fcf2025 - (Decimal(str(r25q1.NETCASH_OPERATE))-Decimal(str(r25q1.CONSTRUCT_LONG_ASSET))) + (Decimal(str(r26q1.NETCASH_OPERATE))-Decimal(str(r26q1.CONSTRUCT_LONG_ASSET)))
print('fcf_ttm_yi',fcfttm/Decimal('1e8'),'yield',fcfttm/market_cap*100)
# debt/ev 2026 q1 and 2025
for d in ['2025-12-31','2026-03-31']:
 bal=pd.read_csv('reports/长江电力/sources/ak_balance_em.csv'); bal['date']=pd.to_datetime(bal['REPORT_DATE']).dt.strftime('%Y-%m-%d')
 r=bal[bal.date==d].iloc[0]
 debt=sum(Decimal(str(getattr(r,c,0) if pd.notna(getattr(r,c,0)) else 0)) for c in ['SHORT_LOAN','NONCURRENT_LIAB_1YEAR','LONG_LOAN','BOND_PAYABLE','LEASE_LIAB'])
 cash=Decimal(str(r.MONETARYFUNDS))
 ev=market_cap+debt-cash
 print(d,'debt_yi',debt/Decimal('1e8'),'cash_yi',cash/Decimal('1e8'),'net_debt_yi',(debt-cash)/Decimal('1e8'),'ev_yi',ev/Decimal('1e8'),'debt_assets',Decimal(str(r.TOTAL_LIABILITIES))/Decimal(str(r.TOTAL_ASSETS))*100,'current_ratio',Decimal(str(r.TOTAL_CURRENT_ASSETS))/Decimal(str(r.TOTAL_CURRENT_LIAB)))
# operating margins years
profit=pd.read_csv('reports/长江电力/sources/selected_profit.csv')
cashsel=pd.read_csv('reports/长江电力/sources/selected_cash.csv')
bal=pd.read_csv('reports/长江电力/sources/selected_balance.csv')
for _,r in profit[profit.date!='2026-03-31'].iterrows():
 rev=Decimal(str(r.TOTAL_OPERATE_INCOME)); op=Decimal(str(r.OPERATE_PROFIT)); np=Decimal(str(r.PARENT_NETPROFIT)); cost=Decimal(str(r.OPERATE_COST));
 print(r.date,'gross_margin',(rev-cost)/rev*100,'op_margin',op/rev*100,'net_margin',np/rev*100)
