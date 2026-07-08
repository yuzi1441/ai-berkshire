import requests, json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search','X-Requested-With':'XMLHttpRequest'}
for sk in ['聘任 总经理','高级管理人员','补选董事 高级管理人员','总会计师','总法律顾问','董事辞职']:
 data={'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'sz','stock':'000400,gssz0000400','searchkey':sk,'secid':'','category':'','trade':'','seDate':'2025-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',headers=headers,data=data,timeout=20)
 print('\n==',sk, r.status_code)
 j=r.json(); print('total',j.get('totalAnnouncement'))
 for a in (j.get('announcements') or [])[:20]:
  print(a['announcementTime'],a['announcementId'],a['announcementTitle'].replace('<em>','').replace('</em>',''),a['adjunctUrl'])