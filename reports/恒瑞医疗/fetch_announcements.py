import urllib.request, urllib.parse, json, datetime, pathlib, re
stock='600276,gssh0600276'
records=[]
for page in range(1,5):
  data=urllib.parse.urlencode({'stock':stock,'tabName':'fulltext','pageSize':'50','pageNum':str(page),'column':'sse','plate':'sh','seDate':'2026-01-01~2026-07-06','searchkey':'','isHLtitle':'true'}).encode()
  req=urllib.request.Request('http://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/','Content-Type':'application/x-www-form-urlencoded'})
  obj=json.loads(urllib.request.urlopen(req,timeout=20).read().decode('utf-8'))
  for a in obj.get('announcements') or []:
    ts=a.get('announcementTime'); dt=datetime.datetime.fromtimestamp(ts/1000).date().isoformat() if ts else ''
    title=re.sub('<.*?>','',a.get('announcementTitle',''))
    records.append({'date':dt,'title':title,'url':'http://static.cninfo.com.cn/'+a.get('adjunctUrl','')})
pathlib.Path('sources/cninfo_announcements_2026.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
for r in records[:80]: print(r['date'], r['title'], r['url'])