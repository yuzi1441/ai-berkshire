from pypdf import PdfReader
from pathlib import Path
reader=PdfReader('sources/annual2025.pdf')
for start,end,name in [(13,25,'business'),(52,91,'governance'),(92,128,'matters'),(129,139,'shareholders'),(301,309,'fiveyear')]:
    out=[]
    for pn in range(start-1,min(end,len(reader.pages))):
        text=reader.pages[pn].extract_text() or ''
        out.append(f'\n\n=== PDF_PAGE {pn+1} ===\n{text}')
    Path(f'_extract_{name}.txt').write_text('\n'.join(out),encoding='utf-8')
    print(name, 'written')
