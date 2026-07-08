import requests, re, json
s=requests.Session(); s.trust_env=False
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
 'jsonCallBack':'jsonpCallback123456',
 'isPagination':'true',
 'productId':'688271',
 'securityType':'0101,120100,020100,020200,120200',
 'reportType2':'DQBG',
 'pageHelp.pageSize':'25',
 'pageHelp.pageNo':'1',
 'pageHelp.beginPage':'1',
 'pageHelp.cacheSize':'1',
 'pageHelp.endPage':'1',
 '_':'1780000000000'
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/assortment/stock/list/info/announcement/index.shtml?productId=688271'}
r=s.get(url,params=params,headers=headers,timeout=30)
print(r.status_code, r.headers.get('content-type'), len(r.text), r.text[:1000])
open('sources/联影医疗/sse_query.txt','w',encoding='utf-8').write(r.text)
