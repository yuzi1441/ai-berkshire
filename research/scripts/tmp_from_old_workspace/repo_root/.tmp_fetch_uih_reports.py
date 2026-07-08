from pathlib import Path
import requests, re, sys
from bs4 import BeautifulSoup
base=Path('sources/联影医疗')
base.mkdir(parents=True, exist_ok=True)
items=[('2025年报','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12249293&stockid=688271'),('2026Q1','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12249291&stockid=688271')]
for name,url in items:
    r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0'})
    r.raise_for_status()
    html=r.content.decode('gb18030',errors='replace')
    (base/f'{name}_sina.html').write_text(html,encoding='utf-8')
    pdfs=re.findall(r'https?://[^"\']+?\.PDF', html, flags=re.I)
    print(name, 'html_len', len(html), 'pdfs', pdfs[:3])
    text=BeautifulSoup(html,'html.parser').get_text('\n')
    (base/f'{name}_sina_text.txt').write_text(text,encoding='utf-8')
    if pdfs:
        pdf_url=pdfs[0]
        pr=requests.get(pdf_url,timeout=60,headers={'User-Agent':'Mozilla/5.0'})
        print('pdf', pr.status_code, pr.headers.get('content-type'), len(pr.content), pdf_url)
        if pr.content[:4] == b'%PDF':
            (base/f'{name}.pdf').write_bytes(pr.content)
        else:
            (base/f'{name}_pdf_bad.bin').write_bytes(pr.content[:1000])
print('done', base.resolve())
