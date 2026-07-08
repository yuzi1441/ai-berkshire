import requests, json
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
base={'tabName':'fulltext','pageSize':'20','pageNum':'1','column':'szse','plate':'','seDate':'2025-01-01~2026-07-06'}
for params in [
 {'searchkey':'华明装备'},
 {'searchkey':'002270'},
 {'stock':'002270,gssz0002270','searchkey':''},
 {'stock':'002270','searchkey':''},
 {'stock':'华明装备,002270','searchkey':''},
]:
 data=base.copy(); data.update(params)
 r=s.post(url,data=data,headers=headers,timeout=20)
 print('\nPARAM',params,'status',r.status_code,'len',len(r.text), r.text[:120])
 try:
  j=r.json(); print('totalRecordNum',j.get('totalRecordNum'))
  for a in (j.get('announcements') or [])[:5]:
   print(a.get('announcementTitle'), a.get('announcementTime'), a.get('adjunctUrl'), a.get('secCode'), a.get('secName'), a.get('orgId'))
 except Exception as e: print('json err',e)