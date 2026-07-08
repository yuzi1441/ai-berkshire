import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=601398&orgId=jjxt0000019'}
base={'stock':'601398,jjxt0000019','tabName':'fulltext','pageSize':'30','pageNum':'1','column':'sse','plate':'sh','seDate':'2026-01-01~2026-07-07','isHLtitle':'true'}
for cat in ['category_ndbg_szsh;','category_yjdbg_szsh;','category_ndbg_szsh;category_yjdbg_szsh;','']:
 data=base.copy(); data['category']=cat
 r=requests.post(url,data=data,headers=headers,timeout=20); print('cat',cat,r.status_code,r.text[:1000])
