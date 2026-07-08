import requests,json,datetime
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
data={'pageNum':1,'pageSize':50,'column':'szse','tabName':'fulltext','plate':'sz','stock':'300760,9900035304','searchkey':'','secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
r=requests.post(url,headers=headers,data=data,timeout=20)
j=r.json(); print('total',j.get('totalAnnouncement'))
for a in j.get('announcements') or []:
    t=datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d') if a.get('announcementTime') else ''
    print(t,a['announcementTitle'],a['adjunctUrl'])
