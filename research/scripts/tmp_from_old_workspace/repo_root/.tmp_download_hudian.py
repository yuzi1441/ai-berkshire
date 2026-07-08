import requests, re, os
from pathlib import Path
ids={'2025AR':'12014866','2026Q1':'12144419','IR20260706':'12432774'}
out=Path('sources/沪电股份'); out.mkdir(parents=True, exist_ok=True)
headers={'User-Agent':'Mozilla/5.0'}
for name,id in ids.items():
    detail=f'https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id={id}&stockid=002463'
    r=requests.get(detail,headers=headers,timeout=20)
    text=r.content.decode('gb18030','ignore')
    m=re.search(r"href='(http://file\.finance\.sina\.com\.cn/[^']+\.PDF)'", text, re.I)
    print(name, id, 'detail', r.status_code, 'pdf', m.group(1) if m else None)
    if m:
        pdf_url=m.group(1)
        pr=requests.get(pdf_url,headers=headers,timeout=60)
        print(' pdf resp', pr.status_code, pr.headers.get('content-type'), len(pr.content), pr.content[:4])
        path=out/(name+'.pdf')
        path.write_bytes(pr.content)
        print(path.resolve())
