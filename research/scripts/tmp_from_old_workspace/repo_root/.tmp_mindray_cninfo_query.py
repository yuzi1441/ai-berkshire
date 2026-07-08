import requests,json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=300760&orgId=9900035957'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
for stock in ['300760,9900035957','300760,gssz000300760','300760']:
 for key in ['2025年年度报告','2026年第一季度报告','年度报告','一季度报告']:
  data={'pageNum':1,'pageSize':20,'column':'szse','tabName':'fulltext','plate':'sz','stock':stock,'searchkey':key,'secid':'','category':'','trade':'','seDate':'2025-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
  try:
   r=requests.post(url,data=data,headers=headers,timeout=20)
   print('\nstock',stock,'key',key,'status',r.status_code, r.text[:80])
   js=r.json()
  except Exception as e: print('err',e); continue
  print('total',js.get('totalAnnouncement'))
  for a in (js.get('announcements') or [])[:8]:
   print(a.get('announcementTitle'), a.get('announcementTime'), a.get('adjunctUrl'), a.get('orgId'), a.get('announcementId'))
