import requests,json
url='http://www.cninfo.com.cn/new/fulltextSearch/full'
params={'searchkey':'迈瑞医疗 2025年年度报告','sdate':'2026-01-01','edate':'2026-07-06','isfulltext':'false','sortName':'pubdate','sortType':'desc','pageNum':'1'}
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/fulltextSearch'}
r=requests.get(url,headers=headers,params=params,timeout=20)
print(r.url)
print(r.status_code)
print(r.text[:2000])
