import requests, json, datetime
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={'tabName':'fulltext','pageSize':'100','pageNum':'1','column':'szse','plate':'','seDate':'2025-01-01~2026-07-06','searchkey':'华明装备'}
j=s.post(url,data=data,headers=headers,timeout=20).json()
for a in j.get('announcements') or []:
 title=a.get('announcementTitle','')
 if any(k in title for k in ['年度报告','第一季度报告','半年度报告','第三季度报告','权益分派','利润分配','回报规划','员工持股','投资者关系活动记录']):
  print(datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d'), title, 'https://static.cninfo.com.cn/'+a['adjunctUrl'])