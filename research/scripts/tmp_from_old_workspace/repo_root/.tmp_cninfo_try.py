import requests, json
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
for stock in ['002463','002463,沪电股份','002463,gssz0002463']:
 data={'pageNum':'1','pageSize':'10','column':'szse','tabName':'fulltext','plate':'sz','stock':stock,'searchkey':'沪电股份','category':'','seDate':'2026-01-01~2026-07-06','isHLtitle':'true'}
 r=s.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,timeout=20)
 print('STOCK',stock, r.status_code, r.text[:500])
