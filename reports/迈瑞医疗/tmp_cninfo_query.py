import requests, json, datetime
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=300760&orgId=9900022601'}
data={
 'stock':'300760,gfbj0834966',
 'tabName':'fulltext',
 'pageSize':30,
 'pageNum':1,
 'column':'szse',
 'category':'category_ndbg_szsh;',
 'plate':'sz',
 'seDate':'2026-01-01~2026-07-06',
 'searchkey':'',
 'secid':'',
 'sortName':'',
 'sortType':'',
 'isHLtitle':'true'
}
r=requests.post(url,data=data,headers=headers)
print(r.status_code, r.text[:2000])
