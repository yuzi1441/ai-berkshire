import requests, json
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/disclosure/stock?stockCode=600312&orgId=gssh0600312'}
data={'stock':'600312,gssh0600312','tabName':'fulltext','pageSize':'30','pageNum':'1','column':'sse','category':'category_ndbg_szsh;category_yjdbg_szsh;category_bndbg_szsh;category_yjyyjxz_szsh;','plate':'sh','seDate':'2025-01-01~2026-07-07','searchkey':''}
r=s.post(url,data=data,headers=headers,timeout=20)
print(r.status_code,r.text[:500])
j=r.json(); print(json.dumps(j,ensure_ascii=False,indent=2)[:5000])
