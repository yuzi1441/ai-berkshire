import requests, json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/fulltextSearch'}
url='http://www.cninfo.com.cn/new/fulltextSearch/full'
for kw in ['迈瑞医疗 2025年年度报告','迈瑞医疗 2026年第一季度报告','300760 2025年年度报告','300760 2026年第一季度报告']:
 data={'searchkey':kw,'sdate':'2026-01-01','edate':'2026-07-06','isfulltext':'false','sortName':'pubdate','sortType':'desc','pageNum':1,'pageSize':10}
 r=requests.post(url,data=data,headers=headers,timeout=20)
 print('\nKW',kw,'status',r.status_code,'len',len(r.text))
 print(r.text[:2000])
