import requests, datetime, json, re
from pathlib import Path
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
keys=['平高电气','600312']
out=[]
for key in keys:
  data={'tabName':'fulltext','pageSize':'100','pageNum':'1','column':'sse','plate':'','seDate':'2020-01-01~2026-07-07','searchkey':key}
  try:
    j=s.post(url,data=data,headers=headers,timeout=30).json()
  except Exception as e:
    out.append({'key':key,'err':repr(e)}); continue
  for a in j.get('announcements') or []:
    title=a.get('announcementTitle','')
    if any(k in title for k in ['年度报告','第一季度报告','半年度报告','第三季度报告','权益分派','利润分配','现金分红','回报规划','员工持股','股权激励','投资者关系活动记录','业绩说明会','董事会','关联交易','回购','并购','收购','担保','募集资金']):
      out.append({
        'key':key,
        'date':datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d'),
        'title':title,
        'url':'https://static.cninfo.com.cn/'+a['adjunctUrl'],
        'id':a.get('announcementId')
      })
Path('sources/pgdq/cninfo_filtered_announcements.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
for x in out[:120]: print(x['date'], x['title'], x['url'])
print('count',len(out))
