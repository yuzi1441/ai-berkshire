from bs4 import BeautifulSoup
from pathlib import Path
for name in ['annual','q1']:
    text=Path(f'.tmp_sina_{name}.html').read_text(encoding='utf-8')
    soup=BeautifulSoup(text,'html.parser')
    plain=soup.get_text('\n')
    for kw in ['重要提示', '主要会计数据', '营业收入', '归属于上市公司股东的净利润', '经营活动产生的现金流量净额','分季度主要财务指标','报告期末普通股股东总数','PDF下载公告']:
        idx=plain.find(kw)
        print('\n---',name,kw,idx,'---')
        if idx>=0: print(plain[idx:idx+2000])
    # capture all href with pdf/cninfo
    print('\nlinks')
    for a in soup.find_all('a', href=True):
        h=a['href']; t=a.get_text(strip=True)
        if 'PDF' in t or 'pdf' in h.lower() or 'cninfo' in h.lower() or 'download' in h.lower(): print(t,h)
