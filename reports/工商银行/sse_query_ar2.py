import requests, json
codes=['601398','601288','601328','600036']
queries=['年度报告','2025年度报告','2025 年度报告','2025年报']
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
headers={'Referer':'https://www.sse.com.cn/assortment/stock/list/info/announcement/','User-Agent':'Mozilla/5.0'}
for code in codes:
    print('\nCODE',code)
    for kw in queries:
        params={
        'isPagination':'true','productId':code,'keyWord':kw,'securityType':'0101,120100,020100,020200,120200','reportType':'ALL','beginDate':'2026-01-01','endDate':'2026-05-10','pageHelp.pageSize':'10','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'1'}
        r=requests.get(url,params=params,headers=headers,timeout=20); r.encoding='utf-8'; d=r.json();
        data=d['pageHelp']['data']
        print(' kw',kw,'n',len(data))
        for x in data[:5]:
            print(json.dumps({k:x.get(k) for k in ['SECURITY_CODE','SECURITY_NAME','TITLE','URL','SSEDATE','ADDDATE']},ensure_ascii=False))
