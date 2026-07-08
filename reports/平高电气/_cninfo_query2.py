import requests
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
for key in ['第一季度报告','2026年第一季度报告','平高电气']:
 data={'pageNum':'1','pageSize':'20','column':'sse','tabName':'fulltext','plate':'sse','stock':'600312,gssh0600312','searchkey':key,'category':'','seDate':'2026-04-01~2026-05-10','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post(url,headers=headers,data=data,timeout=20)
 print('\nKEY',key,'status',r.status_code)
 j=r.json(); print('total', j.get('totalRecordNum'))
 for ann in (j.get('announcements') or [])[:10]:
  print(ann.get('announcementTitle'), ann.get('adjunctUrl'), ann.get('announcementTime'))
