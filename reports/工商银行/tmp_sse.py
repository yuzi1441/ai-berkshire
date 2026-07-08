import requests, json, pathlib
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
'isPagination':'true','productId':'601988','keyWord':'2026年第一季度报告','securityType':'0101,120100,020100,020200,120200','reportType':'ALL','beginDate':'2026-04-01','endDate':'2026-05-10','pageHelp.pageSize':'20','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'1'}
headers={'Referer':'https://www.sse.com.cn/assortment/stock/list/info/announcement/','User-Agent':'Mozilla/5.0'}
r=requests.get(url,params=params,headers=headers,timeout=20)
r.encoding='utf-8'
d=r.json()
for x in d['pageHelp']['data']:
    print(json.dumps({k:x.get(k) for k in ['SECURITY_CODE','SECURITY_NAME','TITLE','BULLETIN_YEAR','BULLETIN_TYPE','URL','SSEDATE','ADDDATE']},ensure_ascii=False))
