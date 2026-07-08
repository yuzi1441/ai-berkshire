import pandas as pd, pathlib
base=pathlib.Path('data/eastone_000682_raw')
ind=pd.read_csv(base/'fin_ind_report.csv')
profit=pd.read_csv(base/'profit_report.csv')
bal=pd.read_csv(base/'balance_report.csv')
cash=pd.read_csv(base/'cash_report.csv')
# annual rows Dec for 2021-2025 plus q1 2026
rows=[]
for year in range(2021,2026):
    d=f'{year}-12-31 00:00:00'
    a=ind[ind.REPORT_DATE==d].iloc[0]
    p=profit[profit.REPORT_DATE==d].iloc[0]
    b=bal[bal.REPORT_DATE==d].iloc[0]
    c=cash[cash.REPORT_DATE==d].iloc[0]
    rows.append(dict(period=f'{year}A', revenue=a.TOTALOPERATEREVE/1e8, gross_profit=a.MLR/1e8, gross_margin=a.XSMLL, net_profit=a.PARENTNETPROFIT/1e8, deduct_np=a.KCFJCXSYJLR/1e8, ocf=c.NETCASH_OPERATE/1e8 if 'NETCASH_OPERATE' in c else a.MGJYXJJE*1340599269/1e8, research=p.RESEARCH_EXPENSE/1e8, asset_liab=a.ZCFZL, eps=a.EPSJB, bps=a.BPS, roe=a.ROEJQ))
# q1
for d,label in [('2026-03-31 00:00:00','2026Q1')]:
    a=ind[ind.REPORT_DATE==d].iloc[0]; p=profit[profit.REPORT_DATE==d].iloc[0]; c=cash[cash.REPORT_DATE==d].iloc[0]
    rows.append(dict(period=label, revenue=a.TOTALOPERATEREVE/1e8, gross_profit=a.MLR/1e8, gross_margin=a.XSMLL, net_profit=a.PARENTNETPROFIT/1e8, deduct_np=a.KCFJCXSYJLR/1e8, ocf=c.NETCASH_OPERATE/1e8 if 'NETCASH_OPERATE' in c else a.MGJYXJJE*1340599269/1e8, research=p.RESEARCH_EXPENSE/1e8, asset_liab=a.ZCFZL, eps=a.EPSJB, bps=a.BPS, roe=a.ROEJQ, rev_yoy=a.TOTALOPERATEREVETZ, np_yoy=a.PARENTNETPROFITTZ))
print(pd.DataFrame(rows).round(4).to_string(index=False))
print('cash cols', [c for c in cash.columns if 'NET' in c and 'CASH' in c][:20])
