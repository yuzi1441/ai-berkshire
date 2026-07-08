import requests, json
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
'isPagination':'true','productId':'601398','keyWord':'','securityType':'0101,120100,020100,020200,120200','reportType2':'DQBG','reportType':'ALL','beginDate':'2026-04-01','endDate':'2026-04-30','pageHelp.pageSize':'25','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'1'}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
r=requests.get(url,params=params,headers=headers,timeout=20)
print(r.url)
print(r.status_code,r.headers.get('content-type'),r.text[:1000])