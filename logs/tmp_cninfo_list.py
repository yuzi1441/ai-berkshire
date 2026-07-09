import requests, json, datetime, pathlib
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
all=[]
for page in range(1,4):
 data={'stock':'600420,gssh0600420','tabName':'fulltext','pageSize':'30','pageNum':str(page),'column':'sse','category':'','plate':'sh','seDate':'2026-01-01~2026-07-08','searchkey':'','secid':'','sortName':'','sortType':'','isHLtitle':'true'}
 js=requests.post(url,headers=headers,data=data,timeout=30).json()
 for a in js.get('announcements') or []:
  ts=a.get('announcementTime')
  dt=datetime.datetime.fromtimestamp(ts/1000).date() if ts else ''
  print(dt, a['announcementId'], a['announcementTitle'], a['adjunctUrl'])
