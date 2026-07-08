from pathlib import Path
import pdfplumber
for pdf in Path('source_docs/pgdq').glob('*.pdf'):
    out=pdf.with_suffix('.txt')
    if out.exists() and out.stat().st_size>1000 and 'bundle' not in out.name:
        # keep existing? overwrite extras only by extracting all to keep readable
        pass
    texts=[]
    try:
        with pdfplumber.open(str(pdf)) as p:
            for i,page in enumerate(p.pages,1):
                txt=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
                texts.append(f'\n\n--- page {i} ---\n'+txt)
        out.write_text('\n'.join(texts), encoding='utf-8')
        print(out, out.stat().st_size)
    except Exception as e:
        print('ERR', pdf, e)
