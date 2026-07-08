from bs4 import BeautifulSoup
from pathlib import Path
import pandas as pd, re
html=Path('sources/beigene_management/2026_proxy.html').read_text(encoding='utf-8')
soup=BeautifulSoup(html,'html.parser')
# Print tables containing certain terms
terms=['Summary Compensation Table','John V. Oyler','Security Ownership','Amgen','Rosenberg','Xiaobin Wu','Related Person Transactions']
for ti,table in enumerate(soup.find_all('table')):
    txt=table.get_text(' ',strip=True)
    if any(t in txt for t in terms):
        print('\nTABLE',ti,'len',len(txt))
        print(txt[:4000])
