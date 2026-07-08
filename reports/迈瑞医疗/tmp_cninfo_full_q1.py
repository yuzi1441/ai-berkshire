import requests
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/fulltextSearch'}
url='http://www.cninfo.com.cn/new/fulltextSearch/full'
queries=['迈瑞医疗 第一季度报告','迈瑞医疗 2026 第一季度','300760 第一季度报告','迈瑞医疗 2026年一季度报告','迈瑞医疗 2026年第一季度报告全文']
for kw in queries:
 data={'searchkey':kw,'sdate':'2026-01-01','edate':'2026-07-06','isfulltext':'false','sortName':'pubdate','sortType':'desc','pageNum':1,'pageSize':20}
 r=requests.post(url,data=data,headers=headers,timeout=20)
 print('\nKW',kw,'status',r.status_code,'len',len(r.text))
 print(r.text[:1500])
