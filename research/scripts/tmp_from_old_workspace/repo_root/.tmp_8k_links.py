from bs4 import BeautifulSoup
from pathlib import Path
import re
for file in ['2026_0626_8K.html','2026_0611_8K.html','2026_0513_8K.html']:
    html=(Path('sources/sec_beone')/file).read_text(encoding='utf-8',errors='ignore')
    soup=BeautifulSoup(html,'html.parser')
    links=[(a.get_text(' ',strip=True),a.get('href')) for a in soup.find_all('a') if a.get('href')]
    print('\n###',file)
    print(links[:20])
    text=soup.get_text('\n')
    for pat in ['Item 8.01','Item 7.01','Exhibit 99.1','Annual General Meeting','EGFR','sonrotoclax','TEVIMBRA','BRUKINSA']:
        i=text.lower().find(pat.lower())
        if i!=-1:
            print('PAT',pat, re.sub(r'\n{2,}','\n',text[i:i+1200]))