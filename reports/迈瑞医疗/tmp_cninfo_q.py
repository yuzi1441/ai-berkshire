import requests,json
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
for cat in ['category_yjdbg_szsh','category_sjdbg_szsh','category_jdbg_szsh','category_bndbg_szsh','category_qtr_szsh','']:
 data={'pageNum':1,'pageSize':10,'column':'szse','tabName':'fulltext','plate':'sz','stock':'300760,9900035304','searchkey':'2026年第一季度报告','secid':'','category':cat,'trade':'','seDate':'2026-01-01~2026-07-06','sortName':'','sortType':'','isHLtitle':'true'}
 r=requests.post(url,headers=headers,data=data,timeout=20)
 print('\ncat',cat,'status',r.status_code)
 j=r.json(); print(j.get('totalAnnouncement'), json.dumps(j.get('announcements')[:3] if j.get('announcements') else None,ensure_ascii=False,indent=2)[:1500])
