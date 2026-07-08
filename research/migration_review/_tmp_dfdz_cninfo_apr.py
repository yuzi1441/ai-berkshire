import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
data={'stock':'000682,gssz0000682','tabName':'fulltext','pageSize':'60','pageNum':'1','column':'szse','category':'','plate':'sz','seDate':'2026-04-20~2026-04-30','searchkey':'','secid':'','sortName':'','sortType':'','isHLtitle':'true'}
r=requests.post(url,headers=headers,data=data,timeout=20)
js=r.json()
for a in js.get('announcements') or []:
 print(a.get('announcementTime'), a.get('announcementTitle'), a.get('adjunctUrl'))
