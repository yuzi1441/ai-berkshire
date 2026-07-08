import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={'pageNum':1,'pageSize':30,'column':'sse','tabName':'fulltext','plate':'sse','stock':'600276,gssh0600276','searchkey':'','secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
r=requests.post(url,headers=headers,data=data,timeout=20)
print(r.status_code, r.text[:500])
js=r.json()
for ann in js.get('announcements',[])[:30]:
    print(ann.get('announcementTime'), ann.get('announcementTitle'), ann.get('adjunctUrl'))
