import requests, json, re, pathlib, time
base='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
queries=[('2026Q1','2026年第一季度报告','category_yjdbg_szsh','2026-01-01~2026-07-07'),('2025annual','2025年年度报告','category_ndbg_szsh','2026-01-01~2026-07-07'),('2025Q1','2025年第一季度报告','category_yjdbg_szsh','2025-01-01~2025-07-07'),('2025Q3','2025年第三季度报告','category_sjdbg_szsh','2025-01-01~2026-01-01')]
out=[]
for tag,key,cat,dates in queries:
    data={'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'sz','stock':'000682,gssz0000682','searchkey':key,'secid':'','category':cat,'trade':'','seDate':dates,'sortName':'','sortType':'','isHLtitle':'true'}
    r=requests.post(base,headers=headers,data=data,timeout=20)
    print('\n###',tag, r.status_code, r.text[:80])
    j=r.json()
    for ann in j.get('announcements') or []:
        title=re.sub('<.*?>','',ann.get('announcementTitle',''))
        print(tag, title, time.strftime('%Y-%m-%d', time.localtime(ann.get('announcementTime')/1000)), ann.get('adjunctUrl'), ann.get('announcementId'))
        if '摘要' not in title and ('报告' in title): out.append((tag,title,ann.get('adjunctUrl'),ann.get('announcementTime')))
print('OUT',out)