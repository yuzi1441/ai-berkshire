from pathlib import Path
from pypdf import PdfReader
for pdf in Path('sources').glob('ICBC_*_AnnualReport_EN.pdf'):
    out=pdf.with_suffix(pdf.suffix+'.txt')
    if out.exists() and out.stat().st_size>10000:
        print(out,'exists'); continue
    reader=PdfReader(str(pdf))
    chunks=[]
    for i,p in enumerate(reader.pages, start=1):
        try: text=p.extract_text() or ''
        except Exception as e: text=f'[ERR {e}]'
        chunks.append(f'--- PAGE {i} ---\n{text}')
    out.write_text('\n'.join(chunks),encoding='utf-8')
    print(pdf,'pages',len(reader.pages),'chars',sum(len(c) for c in chunks))
