import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=000400&orgId=gssz0000400'}
data={
 'stock':'000400,gssz0000400',
 'tabName':'fulltext',
 'pageSize':30,
 'pageNum':1,
 'column':'szse',
 'category':'category_ndbg_szsh;category_yjdbg_szsh;',
 'plate':'sz',
 'seDate':'2026-01-01~2026-07-07',
 'searchkey':'',
 'secid':'',
 'sortName':'',
 'sortType':'',
 'isHLtitle':'true'
}
r=requests.post(url,headers=headers,data=data,timeout=20)
print(r.status_code, r.url, r.text[:1000])
open('tmp_cninfo.json','w',encoding='utf-8').write(r.text)