import requests, json, re
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
 'jsonCallBack':'jsonpCallback',
 'isPagination':'true',
 'productId':'688271',
 'keyWord':'',
 'securityType':'0101',
 'reportType2':'DQBG',
 'reportType':'ALL',
 'beginDate':'2026-01-01',
 'endDate':'2026-07-06',
 'pageHelp.pageSize':'20',
 'pageHelp.pageNo':'1',
 'pageHelp.beginPage':'1',
 'pageHelp.cacheSize':'1',
 'pageHelp.endPage':'5',
 '_':'1780000000000'
}
headers={'Referer':'https://www.sse.com.cn/','User-Agent':'Mozilla/5.0'}
r=requests.get(url,params=params,headers=headers,timeout=30)
print(r.status_code, r.text[:1000])
