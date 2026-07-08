import requests,json,datetime
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=601088&orgId=9900003701','Content-Type':'application/x-www-form-urlencoded'}
data={
 'pageNum':1,'pageSize':30,'column':'sse','tabName':'fulltext','plate':'sse','stock':'601088,9900003701','searchkey':'','secid':'','category':'category_ndbg_szsh','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
}
r=requests.post(url,headers=headers,data=data,timeout=20)
print(r.status_code,r.url,r.text[:500])
print(r.headers.get('Content-Type'))
try:
 j=r.json(); print(j.keys());
 for ann in j.get('announcements',[])[:5]: print(ann)
except Exception as e: print('json err',e)