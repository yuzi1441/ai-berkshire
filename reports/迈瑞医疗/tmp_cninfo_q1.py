import requests,json
url='http://www.cninfo.com.cn/new/fulltextSearch/full'
for q in ['迈瑞医疗 2026年一季度报告','迈瑞医疗：2026年一季度报告','300760 2026 一季度报告','迈瑞医疗 2026年第一季度']:
  params={'searchkey':q,'sdate':'2026-04-01','edate':'2026-05-10','isfulltext':'false','sortName':'pubdate','sortType':'desc','pageNum':'1'}
  headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/fulltextSearch'}
  r=requests.get(url,headers=headers,params=params,timeout=20)
  print('\nQUERY',q, r.status_code)
  try: data=r.json()
  except Exception as e: print(r.text[:500]); continue
  print('total',data.get('totalAnnouncement'))
  for a in data.get('announcements') or []:
    print(a['announcementTitle'], a['announcementTime'], a['adjunctUrl'])
