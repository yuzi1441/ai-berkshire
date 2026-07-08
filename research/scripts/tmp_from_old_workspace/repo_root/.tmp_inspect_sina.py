from pathlib import Path
import requests, re
from bs4 import BeautifulSoup
for name,url in [('annual','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12249293&stockid=688271'),('q1','https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12249291&stockid=688271')]:
    r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
    text=r.content.decode('gb18030',errors='replace')
    Path(f'sources/uih_{name}_sina.html').parent.mkdir(exist_ok=True)
    Path(f'sources/uih_{name}_sina.html').write_text(text,encoding='utf-8')
    print('\n---',name,'---')
    for pat in ['公告原文','PDF','download','sinafinance','static','f10','vip.stock.finance']:
        print(pat, text.find(pat))
    for m in re.finditer(r'(?:href|src)=["\']([^"\']+)["\']', text):
        u=m.group(1)
        if any(x in u.lower() for x in ['pdf','download','cninfo','sse','notice','static']): print(u[:200])
    soup=BeautifulSoup(text,'html.parser')
    t=soup.get_text('\n')
    print(t[:2000])
    print('len text',len(t))
