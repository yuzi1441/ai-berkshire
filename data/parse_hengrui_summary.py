import json
from pathlib import Path

data=json.loads(Path('data/hengrui_mainfina_all.json').read_text(encoding='utf-8'))
rows=data['result']['data']
raw=Path('data/hengrui_quote_raw.txt').read_text(encoding='utf-8')
fields=raw[raw.find('"')+1:raw.rfind('"')].split('~')
quote={
 'name':'恒瑞医药', 'code':fields[2], 'price':float(fields[3]), 'prev_close':float(fields[4]), 'change_pct':float(fields[32]),
 'high':float(fields[33]), 'low':float(fields[34]), 'turnover_rate':float(fields[38]), 'pe_dynamic':float(fields[39]),
 'float_cap_yi':float(fields[44]), 'market_cap_yi':float(fields[45]), 'pb':float(fields[46]),
 'high_52w':float(fields[47]), 'low_52w':float(fields[48]), 'turnover_amt_wan': float(fields[37]),
 'total_shares':int(fields[73]), 'free_shares':int(fields[72]), 'quote_time':fields[30]
}
annual=[r for r in rows if r['REPORT_TYPE']=='年报'][:5]
q1=[r for r in rows if r['REPORT_DATE_NAME']=='2026一季报'][0]
keep=['REPORT_DATE_NAME','REPORT_DATE','TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR','NETCASH_OPERATE_PK','NETCASH_INVEST_PK','NETCASH_FINANCE_PK','TOTAL_ASSETS_PK','TOTAL_EQUITY_PK','LIABILITY','ROEJQ','ZZCJLL','XSMLL','ZCFZL','EPSJB','BPS','TOTAL_SHARE','RDEXPEND','RDPERSONNEL','PRATIO','FCFF_FORWARD','OPERATE_PROFIT_PK','SALE_ER_PK','RE_RATIO_PK']
summary={'quote':quote,'annual':[{k:r.get(k) for k in keep} for r in annual], 'q1_2026':{k:q1.get(k) for k in keep}}
Path('data/hengrui_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
