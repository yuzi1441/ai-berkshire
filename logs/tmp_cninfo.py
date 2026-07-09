import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={
 'stock':'600420,gssh0600420',
 'tabName':'fulltext',
 'pageSize':'30',
 'pageNum':'1',
 'column':'sse',
 'category':'',
 'plate':'sh',
 'seDate':'2026-01-01~2026-07-08',
 'searchkey':'',
 'secid':'',
 'sortName':'',
 'sortType':'',
 'isHLtitle':'true'
}
r=requests.post(url, headers=headers, data=data, timeout=30)
print(r.status_code, r.headers.get('content-type'), r.text[:500])
try:
    js=r.json(); print(json.dumps(js.get('announcements',[])[:10],ensure_ascii=False,indent=2)[:4000])
except Exception as e: print(e)
