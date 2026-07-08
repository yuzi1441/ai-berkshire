import requests, re, pathlib
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
payload={'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'','stock':'600900,gssh0600900','searchkey':'2025年度股东会','secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
j=s.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',data=payload,timeout=30).json(); print(j.get('totalAnnouncement'))
for a in j.get('announcements') or []:
 title=re.sub('<.*?>','',a['announcementTitle']); print(title,a.get('adjunctUrl'),a.get('announcementId'))
 if a.get('adjunctUrl'):
  p=pathlib.Path('data/长江电力')/(re.sub(r'[\\/:*?"<>|]+','_',title)+'_'+a['announcementId']+'.pdf')
  if not p.exists():
   rr=s.get('http://static.cninfo.com.cn/'+a['adjunctUrl'],timeout=30); print('DL',rr.status_code,len(rr.content));
   if rr.status_code==200: p.write_bytes(rr.content)
