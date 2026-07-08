import requests
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
for se in ['2025-01-01~2026-07-06','2024-01-01~2026-07-06','']:
 data={'pageNum':'1','pageSize':'20','column':'szse','tabName':'fulltext','plate':'sz','stock':'002463,gssz0002463','searchkey':'年度报告','category':'category_ndbg_szsh','seDate':se,'isHLtitle':'true'}
 r=s.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,timeout=20)
 print('SE',se, r.status_code, r.text[:1000])
