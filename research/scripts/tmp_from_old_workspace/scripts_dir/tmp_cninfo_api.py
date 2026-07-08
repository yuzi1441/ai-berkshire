import requests, json
s=requests.Session()
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
data={
 'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'sz','stock':'300760,9900035304','searchkey':'','secid':'','category':'category_ndbg_szsh;','trade':'','seDate':'2026-03-31~2026-03-31','sortName':'','sortType':'','isHLtitle':'true'
}
r=s.post(url,data=data,headers=headers,timeout=20)
print(r.status_code, r.text[:1000])
print(r.headers.get('content-type'))
try:
 j=r.json(); print(json.dumps(j,ensure_ascii=False,indent=2)[:4000])
except Exception as e: print(e)
