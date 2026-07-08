from pathlib import Path
import pdfplumber, re, json
base=Path('source_docs/pgdq')
for pdf in [base/'pg_2025_annual.pdf', base/'pg_2026_q1.pdf']:
    out=pdf.with_suffix('.txt')
    with pdfplumber.open(str(pdf)) as p:
        texts=[]
        for i,page in enumerate(p.pages, start=1):
            txt=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            texts.append(f'\n\n--- page {i} ---\n'+txt)
    out.write_text('\n'.join(texts), encoding='utf-8')
    print(out, out.stat().st_size)
