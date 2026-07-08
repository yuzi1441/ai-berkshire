import json, re
from pathlib import Path
root=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire')
annual=json.loads((root/'sources/600276/eastmoney-main-finance-annual-20260706.json').read_text(encoding='utf-8-sig'))['result']['data']
print('year revenue_yi netprofit_yi deduct_yi eps bps ocfps roe gross_margin net_margin debt_ratio rev_growth np_growth')
for r in annual[:10]:
    print(r['REPORT_YEAR'], round(r['TOTALOPERATEREVE']/1e8,2), round(r['PARENTNETPROFIT']/1e8,2), round(r['KCFJCXSYJLR']/1e8,2), r['EPSJB'], round(r['BPS'],2), round(r['MGJYXJJE'],2), r['ROEJQ'], round(r['XSMLL'],2), round(r['XSJLL'],2), round(r['ZCFZL'],2), round(r['TOTALOPERATEREVETZ'],2), round(r['PARENTNETPROFITTZ'],2))
# CAGR 2022 to 2025 revenue/net profit
by={r['REPORT_YEAR']:r for r in annual}
for field,name in [('TOTALOPERATEREVE','revenue'),('PARENTNETPROFIT','net_profit')]:
    start=by['2022'][field]; end=by['2025'][field]
    cagr=(end/start)**(1/3)-1
    print(name,'2022-2025 CAGR',round(cagr*100,2))
# 2016 to 2025 ROE stats
roes=[r['ROEJQ'] for r in annual if r.get('ROEJQ') is not None]
print('roe avg available', round(sum(roes)/len(roes),2), 'min', min(roes), 'max', max(roes))
# fcf approx ocf-capex 2025
ocf=11235378130.63; capex=2961906284.58; shares=6637199874
fcf=ocf-capex
print('fcf 2025 yi', round(fcf/1e8,2), 'fcfps', round(fcf/shares,2), 'fcf_yield at 56.77', round(fcf/(56.77*shares)*100,2))
print('annual_dividend_per_share', 0.2, 'yield', round(0.2/56.77*100,2))
