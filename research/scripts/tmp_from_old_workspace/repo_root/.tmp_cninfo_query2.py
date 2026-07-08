import requests, json
s=requests.Session(); s.trust_env=False
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for cat in ['', 'category_ndbg_szsh', 'category_yjdbg_szsh', 'category_sjdbg_szsh']:
 data={'stock':'002270','tabName':'fulltext','pageSize':'10','pageNum':'1','column':'szse','category':cat,'plate':'sz','seDate':'2025-01-01~2026-07-06','searchkey':'华明装备'}
 r=s.post(url,data=data,headers=headers,timeout=20)
 print('\nCAT',cat,r.status_code,r.text[:200])
 try:
  j=r.json(); print('total',j.get('totalRecordNum'), 'ann', (j.get('announcements') or [])[:1])
 except Exception as e: print(e)