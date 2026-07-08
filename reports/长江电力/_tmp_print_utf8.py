import pdfplumber, json, re
from pathlib import Path
pdf='sources/annual_cypc.pdf'
with pdfplumber.open(pdf) as p:
    for pg in [9,10,11,12,13,14,15,18,19,20,23,24,25,27,28,32,33,46,47,49]:
        txt=p.pages[pg-1].extract_text() or ''
        print('\n===== PAGE',pg,'=====')
        print(txt[:3500])