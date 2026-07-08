import json, requests, os
from pathlib import Path
j=json.loads(Path('cninfo_ann.json').read_text(encoding='utf-8'))
for a in j['announcements']:
    print(a['announcementTitle'], a['announcementTime'], a['adjunctUrl'])
    url='http://static.cninfo.com.cn/'+a['adjunctUrl']
    fn=a['adjunctUrl'].split('/')[-1]
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
    print('download',r.status_code,len(r.content),r.content[:4])
    Path(fn).write_bytes(r.content)