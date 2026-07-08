from pypdf import PdfReader
from pathlib import Path
for fname in ['2023AR_1219650115.pdf','2024AR_1222961962.pdf']:
    p=Path('sources/hengrui')/fname
    reader=PdfReader(str(p))
    print('\n###',fname)
    for idx in range(min(12,len(reader.pages))):
        text=reader.pages[idx].extract_text() or ''
        if '近三年主要会计数据' in text:
            print('PAGE',idx+1)
            print(text[:2200].replace('\n',' | '))
