from pathlib import Path
from bs4 import BeautifulSoup
import re
for file in ['_1228703140703055873.html','_1090677761540059137.html','_966639461867851777.html','_829039716266934273.html','_1210891251105144833.html']:
    p=Path(file)
    if not p.exists():
        continue
    soup=BeautifulSoup(p.read_text(encoding='utf-8',errors='ignore'),'html.parser')
    print('\nFILE',file)
    for a in soup.find_all('a'):
        t=' '.join(a.get_text(' ',strip=True).split())
        href=a.get('href') or ''
        if any(k.lower() in (t+' '+href).lower() for k in ['annual','quarter','result','2025','2024','2023','2022','report','pdf','click']):
            print(t, '=>', href)
