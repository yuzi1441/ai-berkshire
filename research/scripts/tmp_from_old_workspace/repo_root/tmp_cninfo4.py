import requests,json,os,re
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002270','Content-Type':'application/x-www-form-urlencoded'}
for cat in ['category_ndbg_szsh;','category_yjdbg_szsh;','category_sjdbg_szsh;','category_bndbg_szsh;']:
 data={'stock':'002270,9900005198','tabName':'fulltext','pageSize':'30','pageNum':'1','column':'szse','category':cat,'seDate':'2025-01-01~2026-07-06','isHLtitle':'true'}
 r=requests.post(url,headers=headers,data=data,timeout=10)
 print('\nCAT',cat,'STATUS',r.status_code)
 js=r.json(); print('total',js.get('totalAnnouncement'), 'records',js.get('totalRecordNum'))
 for a in (js.get('announcements') or [])[:20]:
  print(a.get('announcementTitle'), a.get('announcementTime'), a.get('adjunctUrl'))
