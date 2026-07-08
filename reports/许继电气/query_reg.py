import requests,json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search','X-Requested-With':'XMLHttpRequest'}
for sk in ['责令改正','警示函','监管措施','河南证监局']:
 data={'pageNum':'1','pageSize':'20','column':'szse','tabName':'fulltext','plate':'sz','stock':'000400,gssz0000400','searchkey':sk,'secid':'','category':'','trade':'','seDate':'2024-01-01~2024-12-31','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',headers=headers,data=data,timeout=20)
 print('\n',sk,r.status_code,r.text[:300])
 j=r.json()
 for a in (j.get('announcements') or []): print(a['announcementTime'],a['announcementId'],a['announcementTitle'].replace('<em>','').replace('</em>',''),a['adjunctUrl'])