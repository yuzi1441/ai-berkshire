import pdfplumber, re, json
from pathlib import Path
for fn in ['2025AR.pdf','2026Q1.pdf','IR20260706.pdf']:
    path=Path('sources/沪电股份')/fn
    print('---',fn,path.stat().st_size)
    with pdfplumber.open(path) as pdf:
        print('pages', len(pdf.pages))
        # print first few pages snippets
        for i in range(min(8,len(pdf.pages))):
            text=pdf.pages[i].extract_text() or ''
            print(f'PAGE {i+1}:', text[:700].replace('\n',' | '))
