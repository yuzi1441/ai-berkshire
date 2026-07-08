from pypdf import PdfReader
from pathlib import Path
for name in ['q1_2026.pdf']:
 reader=PdfReader('sources/'+name)
 out=[]
 for i,p in enumerate(reader.pages):
  out.append(f'\n\n=== PDF_PAGE {i+1} ===\n{p.extract_text() or ""}')
 Path('_extract_q1_2026.txt').write_text('\n'.join(out),encoding='utf-8')
 print(len(reader.pages))
