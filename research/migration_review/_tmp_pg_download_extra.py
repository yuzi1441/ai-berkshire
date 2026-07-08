import requests, json
from pathlib import Path
base=Path('source_docs/pgdq'); base.mkdir(exist_ok=True, parents=True)
items={
 '2025_profit_distribution':'https://static.cninfo.com.cn/finalpage/2026-04-11/1225093695.PDF',
 '2025_dividend_implementation':'https://static.cninfo.com.cn/finalpage/2026-06-18/1225375496.PDF',
 'board_secretary_change':'https://static.cninfo.com.cn/finalpage/2026-06-19/1225378423.PDF',
 'board_2026_04_11':'https://static.cninfo.com.cn/finalpage/2026-04-11/1225093705.PDF',
}
s=requests.Session(); s.trust_env=False
for name,url in items.items():
    p=base/(name+'.pdf')
    if not p.exists() or p.stat().st_size<1000:
        r=s.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'},timeout=60)
        p.write_bytes(r.content)
    print(name,p.stat().st_size,url)
