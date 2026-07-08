import requests
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=601088&orgId=9900003701','Content-Type':'application/x-www-form-urlencoded'}
for kw in ['重组','收购','发行股份','关联交易','分红','权益分派','董事','高级管理人员','总经理','半年报']:
 data={'pageNum':1,'pageSize':50,'column':'sse','tabName':'fulltext','plate':'sse','stock':'601088,9900003701','searchkey':kw,'secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post(url,headers=headers,data=data,timeout=20)
 j=r.json(); anns=j.get('announcements') or []
 print('\nKW',kw,'total',j.get('totalRecordNum'))
 for ann in anns[:20]:
  print(ann['announcementTime'], ann['announcementTitle'].replace('<em>','').replace('</em>',''), ann['adjunctUrl'], ann['announcementId'])