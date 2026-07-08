from bs4 import BeautifulSoup
from pathlib import Path
import re, json, os
for file in ['sources/sec/2026_q1_press.html','sources/sec/2025_fy_press.html','sources/sec/2026_q1_10q.html','sources/sec/2025_10k.html']:
    html=Path(file).read_text(encoding='utf-8',errors='ignore')
    soup=BeautifulSoup(html,'html.parser')
    text=soup.get_text('\n')
    text=re.sub(r'\n\s*\n+', '\n', text)
    out=file+'.txt'
    Path(out).write_text(text,encoding='utf-8')
    print('\n====',file, 'chars',len(text),'====')
    for pat in ['Product revenue','BRUKINSA','Total revenues','Net income','cash','Operating income','GAAP','Full Year 2025','First Quarter 2026','million','billion','weighted-average','ordinary shares']:
        idx=text.lower().find(pat.lower())
        if idx>=0:
            print('---',pat,'---')
            print(text[max(0,idx-500):idx+1200])