import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=000682&orgId=gssz0000682'}
data={'pageNum':1,'pageSize':50,'column':'szse','tabName':'fulltext','plate':'sz','stock':'000682,gssz0000682','searchkey':'','secid':'','category':'category_ndbg_szsh;category_yjdbg_szsh;category_scgkfx_szsh;category_zf_szsh;category_qtr_szsh','trade':'','seDate':'2025-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
r=requests.post(url,headers=headers,data=data,timeout=20)
js=r.json()
for a in js.get('announcements',[]):
    import datetime
    dt=datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d')
    print(dt, a['announcementTitle'], a['adjunctUrl'], a['announcementId'])
