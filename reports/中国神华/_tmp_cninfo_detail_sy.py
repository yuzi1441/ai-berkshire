import requests,re,json
ids=['1225064293','1225185746','1225064313']
for aid in ids:
 url=f'http://www.cninfo.com.cn/new/disclosure/detail?stockCode=601088&announcementId={aid}&orgId=9900003701&announcementTime=2026-03-31'
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=20)
 print('\nID',aid,r.status_code,r.url,len(r.text))
 print(r.text[:500])
 for pat in ['adjunctUrl','announcementTitle','finalpage']:
  print(pat, r.text.find(pat))