import requests,json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/fulltextSearch'}
url='http://www.cninfo.com.cn/new/fulltextSearch/full'
for key in ['迈瑞医疗 2025年年度报告','迈瑞医疗 2026年第一季度报告','300760 2025年年度报告','300760 2026年第一季度报告']:
 params={'searchkey':key,'sdate':'2025-01-01','edate':'2026-07-06','isfulltext':'false','sortName':'pubdate','sortType':'desc','pageNum':1}
 r=requests.get(url,params=params,headers=headers,timeout=20)
 print('\nkey',key,'status',r.status_code,r.url, r.text[:100])
 try: js=r.json()
 except Exception as e: print('jsonerr',e); continue
 print(js.keys(), js.get('totalAnnouncement'))
 for a in (js.get('announcements') or [])[:8]:
  print(a.get('secCode'),a.get('secName'),a.get('announcementTitle'),a.get('announcementTime'),a.get('adjunctUrl'),a.get('announcementId'))
