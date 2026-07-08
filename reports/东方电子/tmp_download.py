from pathlib import Path
import requests
base=Path('sources')
base.mkdir(exist_ok=True)
files={
 '2025_annual.pdf':'http://static.cninfo.com.cn/finalpage/2026-04-24/1225161855.PDF',
 '2026_q1.pdf':'http://static.cninfo.com.cn/finalpage/2026-04-29/1225233627.PDF',
 '2024_annual.pdf':'http://static.cninfo.com.cn/finalpage/2025-04-23/1223215550.PDF',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,url in files.items():
    p=base/name
    if not p.exists() or p.stat().st_size<10000:
        r=requests.get(url,headers=headers,timeout=60)
        print(name,r.status_code,len(r.content),r.headers.get('content-type'))
        p.write_bytes(r.content)
    else:
        print(name,'exists',p.stat().st_size)
