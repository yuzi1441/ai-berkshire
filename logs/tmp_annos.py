import requests, json, datetime, pathlib
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={'stock':'600420,gssh0600420','tabName':'fulltext','pageSize':'80','pageNum':'1','column':'sse','category':'','plate':'sh','seDate':'2026-01-01~2026-07-08','searchkey':'','secid':'','sortName':'','sortType':'','isHLtitle':'true'}
js=requests.post(url,headers=headers,data=data,timeout=30).json()
rows=[]
for a in js.get('announcements') or []:
    dt=datetime.datetime.fromtimestamp(a['announcementTime']/1000).date().isoformat()
    rows.append({'date':dt,'title':a['announcementTitle'],'id':a['announcementId'],'url':'https://static.cninfo.com.cn/'+a['adjunctUrl']})
path=pathlib.Path('data/600420/cninfo_announcements_2026_to_20260708.json')
path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(path.resolve(), len(rows))
for r in rows[:20]: print(r['date'], r['title'], r['url'])
