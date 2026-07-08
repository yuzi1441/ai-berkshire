import requests, pathlib, json, time
items=json.load(open('sources/huaming/cninfo_announcements.json',encoding='utf-8'))
out=pathlib.Path('sources/huaming')
for it in items:
 title=it['announcementTitle']
 if any(k in title for k in ['利润分配','权益分派','年度报告摘要']):
  url='https://static.cninfo.com.cn/'+it['adjunctUrl']
  safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in (it['announcementId']+'_'+title))[:150]+'.PDF'
  p=out/safe
  if not p.exists():
   r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'},timeout=60)
   print(title,r.status_code,len(r.content))
   if r.status_code==200 and r.content[:4]==b'%PDF': p.write_bytes(r.content)
   time.sleep(.1)
