import requests,json
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=601398&orgId=gssh0601398'}
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
for stock in ['601398,gssh0601398','601398','601398,9900013978']:
 for key in ['2025年年度报告','2026年第一季度报告','年度报告','一季度报告','利润分配','资本充足率']:
  data={'pageNum':1,'pageSize':20,'column':'sse','tabName':'fulltext','plate':'sh','stock':stock,'searchkey':key,'secid':'','category':'','trade':'','seDate':'2025-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
  try:
   r=s.post(url,data=data,headers=headers,timeout=20)
   print('\nstock',stock,'key',key,'status',r.status_code, r.text[:80])
   js=r.json()
  except Exception as e: print('err',type(e).__name__,e); continue
  print('total',js.get('totalAnnouncement'))
  for a in (js.get('announcements') or [])[:8]:
   print(a.get('announcementTitle'), a.get('announcementTime'), a.get('adjunctUrl'), a.get('orgId'), a.get('announcementId'))