from pypdf import PdfReader
from pathlib import Path
for p in sorted(Path('sources/hengrui').glob('*.pdf')):
    try:
        reader=PdfReader(str(p))
        print('\n###',p.name,'pages',len(reader.pages))
        text='\n'.join((reader.pages[i].extract_text() or '') for i in range(min(5,len(reader.pages))))
        print(text[:1000].replace('\n',' | '))
    except Exception as e: print(p,e)
