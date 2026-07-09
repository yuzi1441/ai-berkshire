from pathlib import Path
import pdfplumber, re
base=Path('research/source_docs/国药现代')
for pdf in ['国药现代-2025年度报告.pdf','国药现代-2026一季报.pdf']:
    path=base/pdf
    text=[]
    with pdfplumber.open(path) as p:
        print(pdf, 'pages', len(p.pages))
        for i,page in enumerate(p.pages):
            t=page.extract_text() or ''
            if t:
                text.append(f'\n---PAGE {i+1}---\n'+t)
    out=path.with_suffix('.txt')
    out.write_text('\n'.join(text), encoding='utf-8')
    print(out, out.stat().st_size)
