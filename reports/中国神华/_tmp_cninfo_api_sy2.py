import requests,json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=601088&orgId=9900003701','Content-Type':'application/x-www-form-urlencoded'}
for cat,kw in [('category_yjdbg_szsh',''),('','2026年第一季度报告'),('','利润分配')]:
 data={'pageNum':1,'pageSize':30,'column':'sse','tabName':'fulltext','plate':'sse','stock':'601088,9900003701','searchkey':kw,'secid':'','category':cat,'trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post(url,headers=headers,data=data,timeout=20)
 print('\ncat',cat,'kw',kw,r.status_code)
 j=r.json(); print('total',j.get('totalRecordNum'))
 for ann in j.get('announcements',[])[:10]: print(ann['announcementTitle'],ann['announcementTime'],ann['adjunctUrl'],ann['announcementId'])