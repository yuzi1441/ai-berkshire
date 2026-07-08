import urllib.request, urllib.parse, json, pathlib
base='https://datacenter.eastmoney.com/securities/api/data/get'
def fetch(typ, ps=20):
    params={'type':typ,'sty':'ALL','filter':'(SECUCODE="600276.SH")','p':'1','ps':str(ps),'sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
    url=base+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'})
    obj=json.loads(urllib.request.urlopen(req,timeout=30).read().decode('utf-8'))
    return (obj.get('result') or {}).get('data') or []
all_data={}
for typ in ['RPT_F10_FINANCE_MAINFINADATA','RPT_DMSK_FN_INCOME','RPT_DMSK_FN_CASHFLOW','RPT_DMSK_FN_BALANCE']:
    data=fetch(typ,60); all_data[typ]=data
    print('\nTYPE',typ,'count',len(data))
    for r in data[:8]:
        if r.get('REPORT_DATE','')[:10] in ['2025-12-31','2026-03-31','2024-12-31','2023-12-31','2022-12-31','2021-12-31']:
            keys=['REPORT_DATE','REPORT_TYPE','REPORT_DATE_NAME','TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR','BASIC_EPS','EPSJB','TOTAL_OPERATE_INCOME','OPERATE_INCOME','NETPROFIT','PARENT_NETPROFIT','NETCASH_OPERATE','TOTAL_ASSETS','TOTAL_LIABILITIES','MONETARYFUNDS','TOTAL_EQUITY','TOTAL_PARENT_EQUITY','FIXED_ASSET','INVENTORY','R_AND_D_COST','SELL_EXPENSE','OPERATE_COST']
            print({k:r.get(k) for k in keys if k in r})
path=pathlib.Path('sources/eastmoney_600276_financials.json'); path.write_text(json.dumps(all_data,ensure_ascii=False,indent=2),encoding='utf-8'); print('wrote',path)