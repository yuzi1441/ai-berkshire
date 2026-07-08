import requests, re
url='http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600312&announcementId=1225093676&orgId=gssh0600312&announcementTime=2026-04-11'
s=requests.Session();
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
r=s.get(url,headers=headers,timeout=20)
print(r.status_code, r.url, r.text[:1000])
print(re.findall(r'announcementId["\']?\s*[:=]\s*["\']?(\d+)', r.text)[:10])
print(re.findall(r'(finalpage/[^"\']+?\.PDF)', r.text)[:10])
