import requests
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
for key in ['投资者关系','调研','记录表','三季报交流']:
 data={'pageNum':'1','pageSize':'50','column':'szse','tabName':'fulltext','plate':'sz','stock':'002028,gssz0002028','searchkey':key,'secid':'','category':'','trade':'','seDate':'2025-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post(url,headers=headers,data=data,timeout=20)
 print('\nKEY',key, r.json().get('totalAnnouncement'))
 for a in (r.json().get('announcements') or [])[:10]: print(a['announcementTitle'], a['announcementId'], a['adjunctUrl'])