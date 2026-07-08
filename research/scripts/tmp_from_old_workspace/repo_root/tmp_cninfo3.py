import requests,json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002270','Content-Type':'application/x-www-form-urlencoded'}
base={'tabName':'fulltext','pageSize':'30','pageNum':'1','column':'szse','seDate':'2025-01-01~2026-07-06','isHLtitle':'true'}
for stock in ['002270','002270,gssz0002270','002270,9900005198','华明装备,002270']:
 data=base|{'stock':stock}
 r=requests.post(url,headers=headers,data=data,timeout=10)
 print('STOCK',stock,'STATUS',r.status_code)
 try:
  js=r.json(); print('total',js.get('totalAnnouncement'), 'records', js.get('totalRecordNum'))
  anns=js.get('announcements') or []
  for a in anns[:5]: print(a.get('secCode'),a.get('orgId'),a.get('announcementTitle'),a.get('adjunctUrl'))
 except Exception as e: print(r.text[:300])
