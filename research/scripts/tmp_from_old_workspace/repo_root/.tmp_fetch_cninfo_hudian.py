import requests, json, re, sys
from urllib.parse import urlencode
session=requests.Session()
session.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
data={
 'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'sz','stock':'002463,沪电股份','searchkey':'','secid':'','category':'category_ndbg_szsh;category_yjdbg_szsh','trade':'','seDate':'2026-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'
}
r=session.post(url,data=data,timeout=20)
print(r.status_code, r.url, r.text[:200])
print(r.headers.get('content-type'))
print(r.text[:1000])
