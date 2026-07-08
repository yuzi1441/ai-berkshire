from pathlib import Path
import pdfplumber, re, json
for pdf in ['sources/2025_annual.pdf','sources/2026_q1.pdf','sources/2024_annual.pdf']:
    out=Path(pdf).with_suffix('.txt')
    if not out.exists():
        texts=[]
        with pdfplumber.open(pdf) as p:
            print(pdf, len(p.pages))
            for i,page in enumerate(p.pages,1):
                t=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
                texts.append(f"\n--- page {i} ---\n"+t)
        out.write_text('\n'.join(texts),encoding='utf-8')
        print('wrote', out)
    else:
        print('exists', out)
