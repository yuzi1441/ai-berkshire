import requests, json, datetime
from pathlib import Path
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search','X-Requested-With':'XMLHttpRequest'}
def query(searchkey='', category='', seDate='2023-01-01~2026-07-07', pageSize=50):
    data={'pageNum':'1','pageSize':str(pageSize),'column':'szse','tabName':'fulltext','plate':'sz','stock':'000400,gssz0000400','searchkey':searchkey,'secid':'','category':category,'trade':'','seDate':seDate,'sortName':'','sortType':'','isHLtitle':'true'}
    r=requests.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',headers=headers,data=data,timeout=30)
    r.raise_for_status()
    return r.json()
queries=[('annual','年度报告','category_ndbg_szsh;','2023-01-01~2026-07-07'),('q1','第一季度报告','','2026-01-01~2026-07-07'),('chairman','董事长','','2023-01-01~2026-07-07'),('gm','总经理','','2023-01-01~2026-07-07'),('dividend','权益分派 分红','','2023-01-01~2026-07-07'),('repurchase','回购','','2023-01-01~2026-07-07'),('related','关联交易','','2023-01-01~2026-07-07'),('equity','股权激励','','2023-01-01~2026-07-07')]
allres={}
for name,sk,cat,sd in queries:
    try:
        j=query(sk,cat,sd)
    except Exception as e:
        print('ERR',name,e); continue
    allres[name]=j
    print('\n==',name,sk,'total',j.get('totalAnnouncement'))
    for a in (j.get('announcements') or [])[:20]:
        title=a.get('announcementTitle','').replace('<em>','').replace('</em>','')
        print(a['announcementTime'], a['announcementId'], title, a.get('adjunctUrl'))
Path('cninfo_queries.json').write_text(json.dumps(allres,ensure_ascii=False,indent=2),encoding='utf-8')