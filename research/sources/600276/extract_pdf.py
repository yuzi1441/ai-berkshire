from pypdf import PdfReader
from pathlib import Path
root=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\sources\600276')
for name in ['600276-2025-annual.pdf','600276-2026-q1.pdf']:
    p=root/name
    reader=PdfReader(str(p))
    txt=[]
    for i,page in enumerate(reader.pages):
        try:
            t=page.extract_text() or ''
        except Exception as e:
            t=''
        txt.append(f'\n--- PAGE {i+1} ---\n'+t)
    out=p.with_suffix('.txt')
    out.write_text('\n'.join(txt), encoding='utf-8')
    print(name, len(reader.pages), out, out.stat().st_size)
