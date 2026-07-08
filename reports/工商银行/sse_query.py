import requests, json, pathlib, re, os, time
from urllib.parse import urljoin
codes=['601398','601939','601288','601988','601328','601658','600036']
kw='2026年第一季度报告'
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
headers={'Referer':'https://www.sse.com.cn/assortment/stock/list/info/announcement/','User-Agent':'Mozilla/5.0'}
for code in codes:
    params={
    'isPagination':'true','productId':code,'keyWord':kw,'securityType':'0101,120100,020100,020200,120200','reportType':'ALL','beginDate':'2026-04-01','endDate':'2026-05-10','pageHelp.pageSize':'20','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'1'}
    r=requests.get(url,params=params,headers=headers,timeout=20); r.encoding='utf-8'; d=r.json();
    print('\nCODE',code)
    for x in d['pageHelp']['data']:
        print(json.dumps({k:x.get(k) for k in ['SECURITY_CODE','SECURITY_NAME','TITLE','URL','SSEDATE','ADDDATE']},ensure_ascii=False))
