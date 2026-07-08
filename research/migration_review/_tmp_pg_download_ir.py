import requests
from pathlib import Path
base=Path('source_docs/pgdq'); base.mkdir(exist_ok=True, parents=True)
urls={
 'ir_2025_2026q1_20260424':'https://sns.sseinfo.com/resources/images/upload/202604/202604241439058658833478.pdf',
}
s=requests.Session(); s.trust_env=False
for name,u in urls.items():
    p=base/(name+'.pdf')
    r=s.get(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://roadshow.sseinfo.com/'},timeout=60)
    p.write_bytes(r.content)
    print(name, r.status_code, p.stat().st_size, r.headers.get('content-type'))
