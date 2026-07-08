import requests
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={'pageNum':'1','pageSize':'20','column':'szse','tabName':'fulltext','plate':'sz','stock':'002028,gssz0002028','searchkey':'','secid':'','category':'category_ndbg_szsh','trade':'','seDate':'2025-01-01~2025-12-31','sortName':'','sortType':'','isHLtitle':'true'}
r=requests.post(url,headers=headers,data=data,timeout=20)
for a in r.json().get('announcements') or []:
 print(a['announcementTitle'], a['announcementId'], a['adjunctUrl'], a.get('adjunctSize'))