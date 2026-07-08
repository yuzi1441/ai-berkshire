from pypdf import PdfReader
from pathlib import Path
for name in ['lianying_annual_20260429_1225233728.pdf','lianying_q1_20260429_1225233744.pdf']:
    p=Path('sources/联影医疗')/name
    out=Path('sources/联影医疗')/(name+'.pypdf.txt')
    print('extract', p)
    reader=PdfReader(str(p))
    texts=[]
    for i,page in enumerate(reader.pages):
        texts.append(f'\n\n--- page {i+1} ---\n' + (page.extract_text() or ''))
    out.write_text('\n'.join(texts),encoding='utf-8')
    print(out, out.stat().st_size)
