import requests, json, pathlib, re, time
from urllib.parse import quote
out=pathlib.Path(r'reports/华明装备/sources')
out.mkdir(parents=True, exist_ok=True)
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=002270&orgId=gssz0002270'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
stocks=['002270,gssz0002270','002270,9900002270','002270']
keys=['2025年年度报告','2026年第一季度报告','2024年年度报告','2023年年度报告','2022年年度报告','2021年年度报告','年度报告','第一季度报告']
allres=[]
for stock in stocks:
  for key in keys:
    data={'pageNum':1,'pageSize':30,'column':'szse','tabName':'fulltext','plate':'sz','stock':stock,'searchkey':key,'secid':'','category':'','trade':'','seDate':'2021-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
    try:
      r=s.post(url,data=data,headers=headers,timeout=20)
      print('query',stock,key,r.status_code,r.text[:80].replace('\n',' '))
      js=r.json(); js['_stock_query']=stock; js['_key']=key; allres.append(js)
    except Exception as e: print('ERR',stock,key,type(e).__name__,e)
    time.sleep(.2)
(out/'cninfo_queries.json').write_text(json.dumps(allres, ensure_ascii=False, indent=2), encoding='utf-8')
# collect announcements unique with annual/q1 titles
anns=[]; seen=set()
for js in allres:
  for a in js.get('announcements') or []:
    title=re.sub('<.*?>','',a.get('announcementTitle',''))
    if ('年度报告' in title or '第一季度报告' in title or '季度报告' in title) and '摘要' not in title and '取消' not in title and '更正' not in title:
      key=(title,a.get('adjunctUrl'))
      if key not in seen:
        seen.add(key); anns.append(a|{'cleanTitle':title})
print('selected anns',len(anns))
for a in anns[:20]: print(a.get('announcementTime'), a['cleanTitle'], a.get('adjunctUrl'), a.get('announcementId'))
(out/'cninfo_selected_announcements.json').write_text(json.dumps(anns, ensure_ascii=False, indent=2), encoding='utf-8')
# download useful reports
for a in anns:
  title=a['cleanTitle']
  if not any(y in title for y in ['2025','2024','2023','2022','2021','2026年第一季度']): continue
  adj=a.get('adjunctUrl')
  if not adj: continue
  dl='http://static.cninfo.com.cn/'+adj
  safe=re.sub(r'[\\/:*?"<>|\s]+','_',title).strip('_')+'.pdf'
  path=out/safe
  if path.exists() and path.stat().st_size>1000:
    print('exists',safe,path.stat().st_size); continue
  try:
    rr=s.get(dl,headers=headers,timeout=60)
    print('download',title,rr.status_code,rr.headers.get('content-type'),len(rr.content),dl)
    path.write_bytes(rr.content)
  except Exception as e: print('DLERR',title,type(e).__name__,e)
