import requests, json, re, os
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/fulltextSearch?notautosubmit=&keyWord=000682'}
for seDate in ['2026-04-01~2026-07-07','2025-01-01~2026-07-07','2024-01-01~2026-07-07']:
    data={
      'stock':'000682,gssz0000682',
      'tabName':'fulltext',
      'pageSize':'30','pageNum':'1',
      'column':'szse','category':'','plate':'sz','seDate':seDate,
      'searchkey':'','secid':'','sortName':'','sortType':'','isHLtitle':'true'
    }
    try:
      r=requests.post(url,headers=headers,data=data,timeout=20)
      print('status',r.status_code,r.text[:100])
      js=r.json()
      anns=js.get('announcements') or []
      print('seDate',seDate,'count',len(anns),'total',js.get('totalAnnouncement'))
      for a in anns[:20]:
        print(a.get('announcementTime'), a.get('announcementTitle'), a.get('adjunctUrl'))
    except Exception as e: print('ERR',repr(e))
