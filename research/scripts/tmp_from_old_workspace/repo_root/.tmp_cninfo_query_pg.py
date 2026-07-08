import requests, re, json, pandas as pd
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
data={
 'pageNum':1,'pageSize':30,'column':'sse','tabName':'fulltext','plate':'','stock':'600312,gssh0600312','searchkey':'','secid':'','category':'category_ndbg_szsh;','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
}
r=requests.post(url,headers=headers,data=data,timeout=20)
print(r.status_code,r.text[:500])
j=r.json(); print(j.keys()); print(j.get('totalRecordNum'))
for ann in j.get('announcements',[])[:10]: print(ann)
