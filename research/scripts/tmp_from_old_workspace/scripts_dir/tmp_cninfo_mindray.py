import requests, re, json
url='http://www.cninfo.com.cn/new/disclosure/detail?stockCode=300760&announcementId=1225059012&orgId=9900035304&announcementTime=2026-03-31'
s=requests.Session()
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
r=s.get(url,headers=headers,timeout=20)
print(r.status_code, r.url, r.text[:1000])
print('len',len(r.text))
for pat in ['static.szse','adjunctUrl','announcementId','PDF','pdf']:
 print(pat, r.text.find(pat))
 print(re.findall(r'.{0,80}'+re.escape(pat)+r'.{0,120}', r.text)[:3])
