from bs4 import BeautifulSoup
from pathlib import Path
import re
text=BeautifulSoup(Path('sources/sec_beone/2025_10K.html').read_text(encoding='utf-8',errors='ignore'),'html.parser').get_text('\n')
for pat in ['John V. Oyler','Xiaobin Wu','Executive Officers','Founder','Chief Executive Officer','Management Team']:
    i=text.find(pat)
    print('\nPAT',pat,i)
    if i!=-1: print(re.sub(r'\n{2,}','\n',text[max(0,i-800):i+1800])[:2600])