import requests,json,sys
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002270&orgId=gssz0002270'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
for stock in ['002270,gssz0002270','002270','002270,9900002270']:
 for key in ['2025年年度报告','年度报告','2026年第一季度报告','投资者关系活动记录表','社会责任']:
  data={'pageNum':1,'pageSize':20,'column':'szse','tabName':'fulltext','plate':'sz','stock':stock,'searchkey':key,'secid':'','category':'','trade':'','seDate':'2024-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
  r=requests.post(url,data=data,headers=headers,timeout=20)
  print('\nstock',stock,'key',key,'status',r.status_code, r.text[:80])
  try: js=r.json()
  except Exception as e: print('jsonerr',e); continue
  print('total',js.get('totalAnnouncement'))
  for a in (js.get('announcements') or [])[:5]:
   print(a.get('announcementTitle'), a.get('announcementTime'), a.get('adjunctUrl'), a.get('orgId'))
