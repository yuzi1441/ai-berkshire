from pathlib import Path
import pdfplumber, re, json, sys
base=Path('sources/四方股份')
for pdf in base.glob('*.pdf'):
    out=pdf.with_suffix('.txt')
    texts=[]
    with pdfplumber.open(str(pdf)) as p:
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text() or ''
            texts.append(f'\n\n--- PAGE {i} ---\n'+txt)
    out.write_text(''.join(texts),encoding='utf-8')
    print(pdf.name, 'pages', len(texts), 'chars', out.stat().st_size)
