import requests, json, datetime
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=000400&orgId=gssz0000400'}
data={
 'stock':'000400,gssz0000400', 'tabName':'fulltext','pageSize':50,'pageNum':1,'column':'szse',
 'category':'','plate':'sz','seDate':'2026-01-07~2026-07-07','searchkey':'','secid':'','sortName':'','sortType':'','isHLtitle':'true'}
r=requests.post(url,headers=headers,data=data,timeout=20)
j=r.json()
print('total',j.get('totalAnnouncement'))
for a in j.get('announcements',[])[:30]:
 print(a['announcementTitle'], a['announcementTime'], a['adjunctUrl'])
open('tmp_cninfo_6m.json','w',encoding='utf-8').write(json.dumps(j,ensure_ascii=False,indent=2))