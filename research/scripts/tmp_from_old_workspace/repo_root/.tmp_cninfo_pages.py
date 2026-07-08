import requests, datetime
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'; headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
for p in range(1,5):
 data={'tabName':'fulltext','pageSize':'50','pageNum':str(p),'column':'szse','plate':'','seDate':'2025-01-01~2026-07-06','searchkey':'华明装备'}
 j=s.post(url,data=data,headers=headers,timeout=20).json()
 print('PAGE',p,'total',j.get('totalRecordNum'))
 for a in j.get('announcements') or []:
  title=a.get('announcementTitle','')
  if any(k in title for k in ['2025年年度报告','2026年第一季度报告','2025年第三季度报告','2025年半年度报告','年度报告','季度报告','半年度报告','权益分派','回报规划','投资者关系活动记录']):
   print(datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d'), title, 'https://static.cninfo.com.cn/'+a['adjunctUrl'])