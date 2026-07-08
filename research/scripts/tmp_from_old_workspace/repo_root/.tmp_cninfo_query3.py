import requests, json
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/disclosure/stock?stockCode=002270&orgId=gssz0002270'}
data={'stock':'002270,gssz0002270','tabName':'fulltext','pageSize':'20','pageNum':'1','column':'szse','category':'','plate':'sz','seDate':'2025-01-01~2026-07-06','searchkey':''}
r=s.post(url,data=data,headers=headers,timeout=20)
print(r.status_code,r.text[:300])
print(r.url)
try:
 print(json.dumps(r.json(),ensure_ascii=False,indent=2)[:3000])
except Exception as e: print(e)