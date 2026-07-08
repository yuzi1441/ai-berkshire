import requests,json, pathlib, pandas as pd
s=requests.Session(); s.trust_env=False
code='688271'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.eastmoney.com/'}
base='https://datacenter-web.eastmoney.com/api/data/v1/get'
reports=['RPT_F10_FINANCE_MAINFINADATA','RPT_DMSK_FN_INCOME','RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_CASHFLOW']
for report in reports:
    params={'sortColumns':'REPORT_DATE','sortTypes':'-1','pageSize':'20','pageNumber':'1','reportName':report,'columns':'ALL','filter':f'(SECURITY_CODE="{code}")'}
    try:
        j=s.get(base,params=params,headers=headers,timeout=30).json()
        data=(j.get('result') or {}).get('data') or []
        print('\n---',report,'count',len(data),'---')
        pathlib.Path(f'data/uih_{report}.json').write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
        for d in data[:6]:
            keys=['REPORT_DATE','REPORT_TYPE','NOTICE_DATE','EPSJB','BPS','MGJYXJJE','TOTALOPERATEREVE','MLR','PARENTNETPROFIT','KCFJCXSYJLR','TOTALOPERATEREVETZ','PARENTNETPROFITTZ','ROEJQ','ROEKCJQ','XSMLL','XSJLL','ZCFZL','JYXJLL','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_OPERATE_INCOME','OPERATE_INCOME','OPERATE_COST','SALE_EXPENSE','MANAGE_EXPENSE','RESEARCH_EXPENSE','ACCOUNTS_RECE','INVENTORY','CONTRACT_LIAB','MONETARYFUNDS','NETCASH_OPERATE','CONSTRUCT_LONG_ASSET']
            print({k:d.get(k) for k in keys if k in d})
    except Exception as e: print('ERR',report,repr(e))
