from bs4 import BeautifulSoup
from pathlib import Path
import re
fn='2026Q1_10Q.html'
soup=BeautifulSoup((Path('sources/sec_beone')/fn).read_text(encoding='utf-8',errors='ignore'),'html.parser')
text=soup.get_text('\n')
for pat in ['Total revenues','Product revenue, net','BRUKINSA','Net income','Net cash provided','Cash, cash equivalents','Weighted-average shares outstanding','three months ended March 31']:
    for m in re.finditer(re.escape(pat), text, flags=re.I):
        i=m.start(); sn=text[max(0,i-600):i+2200]; sn=re.sub(r'\n{2,}','\n',sn)
        print('\nPAT',pat,'@',i,'\n',sn[:2500])
        break