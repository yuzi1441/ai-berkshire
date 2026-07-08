import requests, time, json
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
'jsonCallBack':'jsonpCallback123456','isPagination':'true','productId':'601126','keyWord':'','securityType':'0101,120100,020100,020200,120200','reportType2':'DQBG','period':'','beginDate':'2025-01-01','endDate':'2026-07-07','pageHelp.pageSize':'25','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5','_':str(int(time.time()*1000))}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/'}
r=requests.get(url,params=params,headers=headers,timeout=20)
print(r.status_code, r.url[:200], len(r.text))
print(r.text[:1000])