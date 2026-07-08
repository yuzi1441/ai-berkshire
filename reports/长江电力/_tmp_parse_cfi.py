from bs4 import BeautifulSoup
from pathlib import Path
html=Path('sources/cfi_2026_h1_power.html').read_text(encoding='utf-8')
soup=BeautifulSoup(html,'html.parser')
text=soup.get_text('\n', strip=True)
print(text[text.find('2026年半年度发电量完成情况公告')-200:text.find('特此公告')+200])
for table in soup.find_all('table'):
    rows=[]
    for tr in table.find_all('tr'):
        cells=[c.get_text(' ', strip=True) for c in tr.find_all(['td','th'])]
        if cells and any('电站' in x or '乌东德' in x for x in cells):
            rows.append(cells)
    if rows:
        for r in rows: print(r)