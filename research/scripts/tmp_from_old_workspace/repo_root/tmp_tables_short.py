from bs4 import BeautifulSoup
from pathlib import Path
html=Path('sources/beigene_management/2026_proxy.html').read_text(encoding='utf-8')
soup=BeautifulSoup(html,'html.parser')
terms=['John V. Oyler','Aaron Rosenberg','Xiaobin Wu','Amgen Inc.']
count=0
out=[]
for ti,table in enumerate(soup.find_all('table')):
    txt=table.get_text(' ',strip=True)
    if any(t in txt for t in terms):
        out.append(f"\nTABLE {ti} len {len(txt)}\n{txt[:2500]}\n")
        count+=1
        if count>=25: break
Path('sources/beigene_management/proxy_tables_short.txt').write_text('\n'.join(out),encoding='utf-8')
print('tables',count)
