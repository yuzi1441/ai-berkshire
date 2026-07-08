from pypdf import PdfReader
from pathlib import Path
for pdf in ['sources/hengrui_20260703_buyback.pdf','sources/hengrui_20260623_ema.pdf','sources/hengrui_20260521_dividend.pdf']:
    r=PdfReader(pdf); text=[]
    for i,p in enumerate(r.pages,1): text.append(f'---PAGE {i}---\n{p.extract_text() or ""}')
    Path(pdf+'.txt').write_text('\n'.join(text),encoding='utf-8')
    print(pdf, len(r.pages)); print('\n'.join(text)[:2000])