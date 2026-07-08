import pandas as pd
from decimal import Decimal, getcontext
getcontext().prec=28
p=pd.read_csv('reports/长江电力/sources/selected_profit.csv')
b=pd.read_csv('reports/长江电力/sources/selected_balance.csv')
# balance has 2020? use raw for previous averages
raw=pd.read_csv('reports/长江电力/sources/ak_balance_em.csv'); raw['date']=pd.to_datetime(raw['REPORT_DATE']).dt.strftime('%Y-%m-%d')
profit=pd.read_csv('reports/长江电力/sources/ak_profit_em.csv'); profit['date']=pd.to_datetime(profit['REPORT_DATE']).dt.strftime('%Y-%m-%d')
for y in [2021,2022,2023,2024,2025]:
 d=f'{y}-12-31'; prev=f'{y-1}-12-31'
 r=profit[profit.date==d].iloc[0]
 b1=raw[raw.date==d].iloc[0]; b0=raw[raw.date==prev].iloc[0]
 avg_assets=(Decimal(str(b1.TOTAL_ASSETS))+Decimal(str(b0.TOTAL_ASSETS)))/2
 avg_equity=(Decimal(str(b1.TOTAL_EQUITY))+Decimal(str(b0.TOTAL_EQUITY)))/2
 net=Decimal(str(r.PARENT_NETPROFIT)); netall=Decimal(str(r.NETPROFIT))
 roa=netall/avg_assets*100
 roe_calc=net/avg_equity*100
 print(y,'ROA',round(roa,2),'ROEcalc equity all',round(roe_calc,2),'avg_assets_yi',round(avg_assets/Decimal('1e8'),1))
