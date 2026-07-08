from bs4 import BeautifulSoup
from pathlib import Path
import re, json
for file in Path('sources/sec_beone').glob('*.html'):
    soup=BeautifulSoup(file.read_text(encoding='utf-8',errors='ignore'),'html.parser')
    text=soup.get_text('\n')
    print('\n---',file.name,'chars',len(text))
    pats=['Revenue','Product revenue','BRUKINSA','TEVIMBRA','Cash','Net income','Net loss','three months ended March 31','year ended December 31','Weighted-average shares']
    for pat in pats:
        i=text.lower().find(pat.lower())
        if i!=-1:
            sn=text[max(0,i-300):i+700]
            sn=re.sub(r'\n{2,}','\n',sn)
            print('\nPAT',pat,'\n',sn[:1200])