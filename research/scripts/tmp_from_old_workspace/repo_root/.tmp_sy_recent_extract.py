import pdfplumber, os
from pathlib import Path
out=[]
for path in Path('sources/002028/recent').glob('*.pdf'):
    try:
        text=[]
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages[:6]: text.append(p.extract_text() or '')
        s='\n'.join(text)
        Path(str(path).replace('.pdf','.txt')).write_text(s,encoding='utf-8')
        out.append('\n--- '+path.name+' ---\n'+s[:3500])
    except Exception as e: out.append(f'{path}: ERR {e}')
Path('data/sy_recent_ann_excerpts.txt').write_text('\n'.join(out),encoding='utf-8')
print('\n'.join(out)[:16000])
