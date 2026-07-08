import requests,json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002270','Content-Type':'application/x-www-form-urlencoded'}
for cat in ['', 'category_ndbg_szsh;', 'category_yjdbg_szsh;', 'category_sjdbg_szsh;', 'category_bndbg_szsh;']:
 data={'stock':'002270','tabName':'fulltext','pageSize':'30','pageNum':'1','column':'szse','category':cat,'seDate':'2025-01-01~2026-07-06','isHLtitle':'true'}
 r=requests.post(url,headers=headers,data=data,timeout=10)
 print('CAT',cat,'STATUS',r.status_code)
 try:
  js=r.json(); print('total',js.get('totalAnnouncement'), 'records', js.get('totalRecordNum'))
  anns=js.get('announcements') or []
  for a in anns[:8]: print(a.get('announcementTitle'), a.get('announcementTime'), a.get('adjunctUrl'))
 except Exception as e: print(r.text[:300])
