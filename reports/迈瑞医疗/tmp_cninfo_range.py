import requests,datetime
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
for seDate in ['2026-04-01~2026-05-05','2026-04-20~2026-04-30','2026-03-01~2026-04-30']:
 data={'pageNum':1,'pageSize':100,'column':'szse','tabName':'fulltext','plate':'sz','stock':'300760,9900035304','searchkey':'','secid':'','category':'','trade':'','seDate':seDate,'sortName':'','sortType':'','isHLtitle':'true'}
 j=requests.post(url,headers=headers,data=data,timeout=20).json(); print('---',seDate,j.get('totalAnnouncement'))
 for a in j.get('announcements') or []:
  t=datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d')
  print(t,a['announcementTitle'],a['adjunctUrl'])
