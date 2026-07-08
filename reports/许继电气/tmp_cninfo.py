import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search','X-Requested-With':'XMLHttpRequest'}
data={
    'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'sz','stock':'000400,gssz0000400','searchkey':'年度报告','secid':'','category':'category_ndbg_szsh;','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
}
r=requests.post(url,headers=headers,data=data,timeout=20)
print(r.status_code, r.text[:500])
print(r.url)
open('cninfo_ann.json','w',encoding='utf-8').write(r.text)