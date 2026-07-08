from pathlib import Path
import pdfplumber, re
for pdf in Path('_sources').glob('*.pdf'):
    text_path = pdf.with_suffix('.txt')
    parts=[]
    with pdfplumber.open(pdf) as p:
        print(pdf, len(p.pages))
        for i,page in enumerate(p.pages,1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            parts.append(f'\n--- page {i} ---\n{text}')
    text_path.write_text('\n'.join(parts), encoding='utf-8')
    print('wrote', text_path, text_path.stat().st_size)