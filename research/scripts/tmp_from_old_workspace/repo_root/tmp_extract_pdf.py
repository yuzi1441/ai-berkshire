from pathlib import Path
import pdfplumber
for pdf in Path('data_sources').glob('*.pdf'):
    print('---', pdf.name)
    txt=[]
    with pdfplumber.open(pdf) as p:
        print('pages', len(p.pages))
        for i,page in enumerate(p.pages[:8]):
            text=page.extract_text() or ''
            txt.append(f'\n---PAGE {i+1}---\n'+text[:4000])
    out=Path(str(pdf)+'.txt')
    out.write_text('\n'.join(txt),encoding='utf-8')
    print('wrote',out)