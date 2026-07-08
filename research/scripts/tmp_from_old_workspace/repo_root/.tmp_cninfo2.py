import requests, json, datetime
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002028&orgId=gssz0002028'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
data={'pageNum':1,'pageSize':20,'column':'szse','tabName':'fulltext','plate':'sz','stock':'002028,gssz0002028','searchkey':'','secid':'','category':'category_ndbg_szsh','trade':'','seDate':'2026-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
r=requests.post(url,data=data,headers=headers,timeout=20)
print(r.status_code)
js=r.json(); print(js.get('totalAnnouncement'))
for a in js.get('announcements') or []:
 print(datetime.datetime.fromtimestamp(a['announcementTime']/1000).date(), a['announcementTitle'], a['adjunctUrl'], a['adjunctSize'])
print('--- q reports')
for cat in ['category_yjdbg_szsh','category_bndbg_szsh','category_sjdbg_szsh']:
 data['category']=cat; data['seDate']='2026-01-01~2026-07-06'; data['searchkey']=''
 r=requests.post(url,data=data,headers=headers,timeout=20); js=r.json(); print('cat',cat,'total',js.get('totalAnnouncement'))
 for a in js.get('announcements') or []: print(datetime.datetime.fromtimestamp(a['announcementTime']/1000).date(), a['announcementTitle'],a['adjunctUrl'],a['adjunctSize'])
