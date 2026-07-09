import requests, json, pathlib, csv, time
codes=['SZ300476','SZ002463','SZ002916','SH600183','SZ002384','SH688183','SH603936','SZ002579']
url='https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}
rows=[]; raw={}
for code in codes:
    r=requests.get(url,params={'type':'0','code':code},headers=headers,timeout=15)
    data=r.json(); raw[code]=data
    allrows=data.get('data') or []
    latest=allrows[0] if allrows else {}
    annual=next((x for x in allrows if str(x.get('REPORT_DATE','')).startswith('2025-12-31')), None)
    for label,x in [('latest',latest),('annual2025',annual or {})]:
        if x:
            rows.append({
                'code':code,'name':x.get('SECURITY_NAME_ABBR'),'period':label,'report_date':x.get('REPORT_DATE'),'report_type':x.get('REPORT_TYPE'),
                'revenue_cny':x.get('TOTALOPERATEREVE'),'revenue_yoy_pct':x.get('TOTALOPERATEREVETZ'),
                'net_profit_parent_cny':x.get('PARENTNETPROFIT'),'net_profit_yoy_pct':x.get('PARENTNETPROFITTZ'),
                'gross_margin_pct':x.get('XSMLL'),'roe_weighted_pct':x.get('ROEJQ'),
                'asset_liability_pct':x.get('ZCFZL'),'ocf_to_revenue':x.get('JYXJLYYSR'),
                'ocf_to_net_profit':x.get('NCO_NETPROFIT'),'sales_net_margin_pct':x.get('XSJLL'),
                'eps_basic':x.get('EPSJB'),'bps':x.get('BPS')
            })
    time.sleep(0.2)
pathlib.Path('data/ai-pcb-materials').mkdir(parents=True,exist_ok=True)
with open('data/ai-pcb-materials/eastmoney_finance_snapshot_20260710.csv','w',newline='',encoding='utf-8-sig') as fp:
    w=csv.DictWriter(fp,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
pathlib.Path('data/ai-pcb-materials/eastmoney_f10_full_20260710.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False,indent=2)[:10000])
