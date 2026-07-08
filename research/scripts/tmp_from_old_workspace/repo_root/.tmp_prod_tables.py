from bs4 import BeautifulSoup
from pathlib import Path
import re
for fn in ['2026Q1_10Q.html','2025_10K.html']:
    text=BeautifulSoup((Path('sources/sec_beone')/fn).read_text(encoding='utf-8',errors='ignore'),'html.parser').get_text('\n')
    print('###',fn)
    for pat in ['The following table disaggregates net product revenue by product', 'net product revenue by product', 'Year Ended December 31', 'Three Months Ended March 31']:
        idx=text.lower().find(pat.lower())
        print(pat, idx)
        if idx!=-1:
            sn=re.sub(r'\n{2,}','\n',text[idx:idx+2500])
            print(sn)
            print('---')