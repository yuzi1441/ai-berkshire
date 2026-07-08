import requests
from pathlib import Path
urls={
 'siyuan_2025_annual_cninfo.pdf':'https://static.cninfo.com.cn/finalpage/2026-04-18/1225117829.PDF',
 'siyuan_2026_q1_cninfo.pdf':'https://static.cninfo.com.cn/finalpage/2026-04-25/1225177123.PDF',
}
s=requests.Session(); s.trust_env=False
for fn,u in urls.items():
    print('download', fn, u)
    r=s.get(u,timeout=60,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
    print(r.status_code, r.headers.get('content-type'), len(r.content), r.content[:5])
    p=Path('sources/思源电气')/fn
    p.write_bytes(r.content)
    print(p, p.stat().st_size)
