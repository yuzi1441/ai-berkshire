import requests, json, re
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={
 'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'sz','stock':'000682,gssz0000682','searchkey':'2025年年度报告','secid':'','category':'category_ndbg_szsh','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
}
r=requests.post(url,headers=headers,data=data,timeout=20)
print(r.status_code, r.text[:500])
try:
    j=r.json();
    for ann in j.get('announcements',[])[:10]:
        print(ann.get('announcementTitle'), ann.get('announcementTime'), ann.get('adjunctUrl'), ann.get('announcementId'))
except Exception as e: print('ERR', e)