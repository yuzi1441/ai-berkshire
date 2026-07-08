import requests, datetime, json
from pathlib import Path
import pdfplumber
base=Path('source_docs/pgdq'); base.mkdir(parents=True, exist_ok=True)
items={
 'pg_2024_annual':'https://static.cninfo.com.cn/finalpage/2025-04-11/1223054837.PDF',
 'pg_2023_annual':'https://static.cninfo.com.cn/finalpage/2024-04-11/1219567393.PDF',
 'pg_2022_annual':'https://static.cninfo.com.cn/finalpage/2023-04-21/1216496824.PDF',
}
s=requests.Session(); s.trust_env=False
for name,url in items.items():
    pdf=base/(name+'.pdf')
    if not pdf.exists() or pdf.stat().st_size<1000:
        r=s.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'},timeout=60)
        pdf.write_bytes(r.content)
    txt=base/(name+'.txt')
    if not txt.exists() or txt.stat().st_size<1000:
        texts=[]
        with pdfplumber.open(str(pdf)) as p:
            for i,page in enumerate(p.pages,1):
                texts.append(f'\n\n--- page {i} ---\n'+(page.extract_text(x_tolerance=1, y_tolerance=3) or ''))
        txt.write_text('\n'.join(texts),encoding='utf-8')
    print(name,pdf.stat().st_size,txt.stat().st_size)
