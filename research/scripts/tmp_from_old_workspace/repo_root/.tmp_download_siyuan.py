import requests
from pathlib import Path
urls={
 'siyuan_2025_annual_sina.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESZ_STOCK/2026/2026-4/2026-04-18/12112020.PDF',
 'siyuan_2026_q1_sina.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESZ_STOCK/2026/2026-4/2026-04-25/12181541.PDF',
}
s=requests.Session(); s.trust_env=False
for fn,u in urls.items():
 print('download',fn,u)
 r=s.get(u,timeout=60,headers={'User-Agent':'Mozilla/5.0'})
 print(r.status_code,r.headers.get('content-type'),len(r.content),r.content[:5])
 p=Path('sources/思源电气')/fn
 p.write_bytes(r.content)
 print(p, p.stat().st_size)
