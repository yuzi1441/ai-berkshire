import requests,json,sys
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sz002028.html'}
# Try zcfz/lrb/xjll via eastmoney report api
for reportName in ['RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_INCOME','RPT_DMSK_FN_CASHFLOW']:
    params={'reportName':reportName,'columns':'ALL','quoteColumns':'','filter':'(SECURITY_CODE="002028")','pageNumber':'1','pageSize':'10','sortTypes':'-1','sortColumns':'REPORT_DATE','source':'HSF10','client':'PC'}
    r=requests.get('https://datacenter.eastmoney.com/securities/api/data/v1/get',params=params,headers=headers,timeout=20)
    print(reportName, r.status_code, r.text[:120])
    try:
        data=r.json().get('result',{}).get('data',[])[:2]
        print(json.dumps(data,ensure_ascii=False,indent=2)[:1500])
    except Exception as e: print(e)
