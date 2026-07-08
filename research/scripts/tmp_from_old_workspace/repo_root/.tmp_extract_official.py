from pypdf import PdfReader
from pathlib import Path
for fname in ['2022AR_1216518776.pdf','2025AR_1225032585.pdf','2026Q1_1225145521.pdf']:
    p=Path('sources/hengrui')/fname
    reader=PdfReader(str(p))
    print('\n###',fname)
    for idx in range(min(12,len(reader.pages))):
        text=reader.pages[idx].extract_text() or ''
        if '近三年主要会计数据' in text or '主要会计数据和财务指标' in text:
            print('PAGE',idx+1)
            print(text[:2500].replace('\n',' | '))
