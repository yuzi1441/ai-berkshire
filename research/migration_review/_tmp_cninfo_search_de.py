import requests, re, time
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
for key in ['第一季度报告','2026第一季度','2026 一季度','季度报告','2026年一季度报告','2026']:
  data={'pageNum':'1','pageSize':'50','column':'szse','tabName':'fulltext','plate':'sz','stock':'000682,gssz0000682','searchkey':key,'secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
  r=requests.post(url,headers=headers,data=data,timeout=20); j=r.json(); print('\nKEY',key,'total',j.get('totalAnnouncement'))
  for ann in (j.get('announcements') or [])[:20]:
    title=re.sub('<.*?>','',ann.get('announcementTitle',''))
    print(time.strftime('%Y-%m-%d', time.localtime(ann.get('announcementTime')/1000)), title, ann.get('adjunctUrl'))