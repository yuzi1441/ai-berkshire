import requests, json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search','X-Requested-With':'XMLHttpRequest'}
for sk in ['2026年第一季度报告','2026年一季度报告','季度报告','2026 第一季度']:
 data={'pageNum':'1','pageSize':'20','column':'szse','tabName':'fulltext','plate':'sz','stock':'000400,gssz0000400','searchkey':sk,'secid':'','category':'category_yjdbg_szsh;','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',headers=headers,data=data,timeout=20)
 print('\n',sk,r.status_code,r.text[:300])