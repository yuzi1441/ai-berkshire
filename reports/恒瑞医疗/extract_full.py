from pypdf import PdfReader
from pathlib import Path
for pdf in ['sources/hengrui_2025_annual.pdf','sources/hengrui_2026_q1.pdf']:
    r=PdfReader(pdf)
    parts=[]
    for i,p in enumerate(r.pages,1):
        try: txt=p.extract_text() or ''
        except Exception as e: txt=''
        parts.append(f'\n---PAGE {i}---\n{txt}')
    Path(pdf+'.full.txt').write_text('\n'.join(parts), encoding='utf-8')
    print(pdf, len(r.pages), 'written')