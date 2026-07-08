import requests, json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002028&orgId=gssz0002028'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
for stock in ['002028,gssz0002028','002028','002028,9900002028']:
 for key in ['2025年年度报告','年度报告','2026年第一季度报告','第一季度报告']:
  data={'pageNum':1,'pageSize':10,'column':'szse','tabName':'fulltext','plate':'sz','stock':stock,'searchkey':key,'secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
  r=requests.post(url,data=data,headers=headers,timeout=20)
  print('stock',stock,'key',key,'status',r.status_code)
  js=r.json(); print('total',js.get('totalAnnouncement'), 'first', (js.get('announcements') or [{}])[0])
