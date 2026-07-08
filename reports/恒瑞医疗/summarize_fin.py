import json
obj=json.load(open('sources/eastmoney_600276_financials.json',encoding='utf-8'))
main=obj['RPT_F10_FINANCE_MAINFINADATA']
cash=obj['RPT_DMSK_FN_CASHFLOW']
bal=obj['RPT_DMSK_FN_BALANCE']
inc=obj['RPT_DMSK_FN_INCOME']
def bydate(data): return {r['REPORT_DATE'][:10]:r for r in data}
C=bydate(cash); B=bydate(bal); I=bydate(inc)
for r in main:
    d=r['REPORT_DATE'][:10]
    if d.endswith('12-31') and d[:4] in ['2021','2022','2023','2024','2025']:
        print(d, 'rev',r.get('TOTALOPERATEREVE'),'np',r.get('PARENTNETPROFIT'),'扣非',r.get('KCFJCXSYJLR'),'eps',r.get('EPSJB'),'bps',r.get('BPS'),'roe',r.get('ROEJQ'),'gm',r.get('XSMLL'),'netmargin',r.get('XSJLL'),'ocf',C.get(d,{}).get('NETCASH_OPERATE'),'capex',C.get(d,{}).get('CONSTRUCT_LONG_ASSET'),'cash',B.get(d,{}).get('MONETARYFUNDS'),'assets',B.get(d,{}).get('TOTAL_ASSETS'),'liab',B.get(d,{}).get('TOTAL_LIABILITIES'),'sell',I.get(d,{}).get('SALE_EXPENSE'),'rd_fee',I.get(d,{}).get('RESEARCH_EXPENSE') or I.get(d,{}).get('R_AND_D_COST'))