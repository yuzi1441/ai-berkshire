from bs4 import BeautifulSoup
from pathlib import Path
import re
for fn in ['2025_10K.html','2026Q1_10Q.html']:
    soup=BeautifulSoup((Path('sources/sec_beone')/fn).read_text(encoding='utf-8',errors='ignore'),'html.parser')
    text=soup.get_text('\n')
    print('\n###',fn)
    for pat in ['Consolidated Statements of Operations','Total revenues','Product revenue, net','BRUKINSA','Product revenue by product','Revenue by Product','Geographic','United States','China','Cash, cash equivalents','Total assets','Net cash provided by operating activities','Free cash flow','Weighted-average shares outstanding']:
        for m in re.finditer(re.escape(pat), text, flags=re.I):
            i=m.start(); sn=text[max(0,i-500):i+1500]; sn=re.sub(r'\n{2,}','\n',sn)
            print('\nPAT',pat,'@',i,'\n',sn[:2000])
            break