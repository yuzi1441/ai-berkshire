import requests, pdfplumber
from pathlib import Path
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for fn,url in {'1219956138_reg_warning.pdf':'finalpage/2024-04-30/1219956138.PDF','1220197679_rectification.pdf':'finalpage/2024-05-30/1220197679.PDF'}.items():
    r=requests.get('http://static.cninfo.com.cn/'+url,headers=headers,timeout=30)
    print(fn,r.status_code,len(r.content),r.content[:4])
    Path(fn).write_bytes(r.content)
    parts=[]
    with pdfplumber.open(fn) as p:
        for i,page in enumerate(p.pages,1): parts.append(f'\n--- PAGE {i} ---\n'+(page.extract_text() or ''))
    Path(fn).with_suffix('.txt').write_text('\n'.join(parts),encoding='utf-8')