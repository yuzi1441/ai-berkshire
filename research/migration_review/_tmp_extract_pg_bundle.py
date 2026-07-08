from pathlib import Path
import pdfplumber
for pdf in [Path('source_docs/pgdq/pg_2025_annual.pdf'), Path('source_docs/pgdq/pg_2026_q1.pdf')]:
    out=pdf.with_name(pdf.stem+'_bundle.txt')
    texts=[]
    with pdfplumber.open(str(pdf)) as p:
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            texts.append(f'\n\n--- page {i} ---\n'+txt)
    out.write_text('\n'.join(texts), encoding='utf-8')
    print(out, out.stat().st_size)
