import requests, json
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for begin,end in [('2026-03-01','2026-04-30'),('2026-01-01','2026-04-30')]:
 params={'isPagination':'true','productId':'601398','keyWord':'','securityType':'0101,120100,020100,020200,120200','reportType2':'DQBG','reportType':'ALL','beginDate':begin,'endDate':end,'pageHelp.pageSize':'50','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'1'}
 r=requests.get(url,params=params,headers=headers,timeout=20)
 data=r.json()['pageHelp']['data']
 print('\nrange',begin,end,'n',len(data))
 for item in data:
  print(item.get('ADDDATE'), item.get('BULLETIN_TYPE'), item.get('TITLE'), item.get('URL'))