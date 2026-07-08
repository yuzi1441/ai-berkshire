import requests, datetime
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'; headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
for key in ['2025年年度报告 华明装备','华明装备 2025年年度报告','华明装备 年度报告']:
 print('\nKEY',key)
 data={'tabName':'fulltext','pageSize':'20','pageNum':'1','column':'szse','plate':'','seDate':'2026-02-01~2026-03-10','searchkey':key}
 j=s.post(url,data=data,headers=headers,timeout=20).json()
 print('total',j.get('totalRecordNum'))
 for a in j.get('announcements') or []:
  print(datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d'), a.get('announcementTitle'), 'https://static.cninfo.com.cn/'+a['adjunctUrl'])