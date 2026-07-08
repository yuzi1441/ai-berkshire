from pathlib import Path
import pdfplumber, re
for pdf in ['icbc_2025_annual_A.pdf','icbc_2026_q1_A.pdf']:
    p=Path(pdf)
    print(pdf, p.exists(), p.stat().st_size)
    with pdfplumber.open(p) as doc:
        print('pages', len(doc.pages))
        text='\n'.join((page.extract_text() or '') for page in doc.pages[:8])
        print(text[:3000])