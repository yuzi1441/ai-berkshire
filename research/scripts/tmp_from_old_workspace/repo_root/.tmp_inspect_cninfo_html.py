import requests, re
url='http://www.cninfo.com.cn/new/disclosure/detail?stockCode=002463&announcementId=1225027832&orgId=9900013929&announcementTime=2026-03-25'
s=requests.Session(); s.trust_env=False
r=s.get(url, timeout=15, headers={'User-Agent':'Mozilla/5.0'})
open('data/cninfo_detail.html','w',encoding='utf-8').write(r.text)
for pat in ['download','static','api','announcement','1225027832','pdf','adjunctUrl']:
 print('PAT',pat, r.text.find(pat))
 for m in re.finditer(pat, r.text):
  print(r.text[max(0,m.start()-150):m.start()+300].replace('\n',' ')[:600]); break
