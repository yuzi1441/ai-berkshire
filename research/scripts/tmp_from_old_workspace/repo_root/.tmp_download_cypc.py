from pathlib import Path
import requests
urls={
 'cypc_2025_annual.pdf':'https://www.cypc.com.cn/cypc/attachDir/2026/05/2026051815345898336.pdf',
 'cypc_2026_q1.pdf':'https://www.ctg.com.cn/cypc/attachDir/2026/05/2026051815335596092.pdf'
}
out=Path('sources/长江电力'); out.mkdir(parents=True, exist_ok=True)
s=requests.Session(); s.trust_env=False
for name,url in urls.items():
    p=out/name
    r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content))
    r.raise_for_status()
    p.write_bytes(r.content)
    print(p.resolve())
