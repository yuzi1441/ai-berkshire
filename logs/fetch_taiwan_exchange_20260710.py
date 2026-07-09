import requests, json, pathlib, csv, urllib3
urllib3.disable_warnings()
twse_targets={'2383','6213','3037','2313','8046','2368','4958','1303'}
tpex_targets={'6274'}
rows=[]
# TWSE price
price = {x['Code']:x for x in requests.get('https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL',timeout=20).json() if x.get('Code') in twse_targets}
val = {x['Code']:x for x in requests.get('https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL',timeout=20).json() if x.get('Code') in twse_targets}
for code in sorted(twse_targets):
    p=price.get(code,{}); v=val.get(code,{})
    rows.append({'market':'TWSE','date':p.get('Date') or v.get('Date'),'code':code,'name':p.get('Name') or v.get('Name'),'close':p.get('ClosingPrice'),'monthly_avg_price':p.get('MonthlyAveragePrice'),'pe':v.get('PEratio'),'pb':v.get('PBratio'),'dividend_yield':v.get('DividendYield')})
# TPEX valuation and close quotes
try:
    tpex_pe=requests.get('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis',timeout=20,verify=False).json()
    tpex_px=requests.get('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes',timeout=20,verify=False).json()
    pe={x.get('SecuritiesCompanyCode'):x for x in tpex_pe if x.get('SecuritiesCompanyCode') in tpex_targets}
    px={x.get('SecuritiesCompanyCode'):x for x in tpex_px if x.get('SecuritiesCompanyCode') in tpex_targets}
    for code in tpex_targets:
        p=px.get(code,{}); v=pe.get(code,{})
        rows.append({'market':'TPEX','date':p.get('Date') or v.get('Date'),'code':code,'name':p.get('CompanyName') or v.get('CompanyName'),'close':p.get('Close'),'monthly_avg_price':'','pe':v.get('PriceEarningRatio'),'pb':v.get('PriceBookRatio'),'dividend_yield':v.get('YieldRatio')})
except Exception as e:
    rows.append({'market':'TPEX','date':'','code':'6274','name':'台燿','close':'ERR','monthly_avg_price':'','pe':repr(e),'pb':'','dividend_yield':''})
pathlib.Path('data/ai-pcb-materials').mkdir(parents=True,exist_ok=True)
with open('data/ai-pcb-materials/taiwan_exchange_valuation_snapshot_20260710.csv','w',newline='',encoding='utf-8-sig') as fp:
    w=csv.DictWriter(fp,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(json.dumps(rows,ensure_ascii=False,indent=2))
