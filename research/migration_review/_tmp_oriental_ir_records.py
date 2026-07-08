import requests, datetime
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
for key in ['东方电子 投资者关系管理信息','东方电子 投资者关系活动记录表','东方电子 2025年度业绩说明会']:
 print('\nKEY',key)
 data={'tabName':'fulltext','pageSize':'100','pageNum':'1','column':'szse','plate':'','seDate':'2021-01-01~2026-07-07','searchkey':key}
 j=s.post(url,data=data,headers=headers,timeout=20).json()
 print('total',j.get('totalRecordNum'))
 for a in (j.get('announcements') or [])[:50]:
  print(datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d'), a.get('announcementTitle'), 'https://static.cninfo.com.cn/'+a['adjunctUrl'])
