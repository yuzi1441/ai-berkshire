from pathlib import Path
import re
text=Path('sources/002028/text/2025AR.txt').read_text(encoding='utf-8')
# extract pages 14-18 around business tables
for page in [14,15,16,17,18,19,20,21,22,23,24,25]:
    m=re.search(rf'--- page {page} ---', text)
    if m:
        m2=re.search(rf'--- page {page+1} ---', text[m.end():])
        end=m.end()+m2.start() if m2 else min(len(text), m.start()+5000)
        print(f'\n---PAGE {page}---')
        print(text[m.start():end].replace('\n',' ')[:5000])
