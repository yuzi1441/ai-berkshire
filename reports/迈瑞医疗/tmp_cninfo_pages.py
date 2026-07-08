import requests,datetime
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
for page in [1,2,3]:
 data={'pageNum':page,'pageSize':50,'column':'szse','tabName':'fulltext','plate':'sz','stock':'300760,9900035304','searchkey':'','secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
 j=requests.post(url,headers=headers,data=data,timeout=20).json()
 print('---page',page,'total',j.get('totalAnnouncement'))
 for a in j.get('announcements') or []:
  title=a['announcementTitle']
  if '季度' in title or '2026年第一季度' in title or '2026年' in title and '报告' in title:
   t=datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d')
   print(t,title,a['adjunctUrl'])
