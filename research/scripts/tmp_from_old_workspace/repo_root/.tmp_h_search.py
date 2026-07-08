import json, pathlib, requests, time
items=json.load(open('sources/huaming/cninfo_announcements.json',encoding='utf-8'))
for it in items:
 title=it['announcementTitle']
 if any(k in title for k in ['H股','境外上市','境外发行','上市备案','香港联合','发行境外']):
  print(it['announcementId'], title, 'https://static.cninfo.com.cn/'+it['adjunctUrl'])
