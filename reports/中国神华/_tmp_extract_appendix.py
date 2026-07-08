from pypdf import PdfReader
from pathlib import Path
reader=PdfReader('sources/annual2025.pdf')
for start,end,name in [(303,310,'appendix')]:
 out=[]
 for pn in range(start-1,min(end,len(reader.pages))):
  text=reader.pages[pn].extract_text() or ''
  out.append(f'\n\n=== PDF_PAGE {pn+1} ===\n{text}')
 Path('_extract_appendix.txt').write_text('\n'.join(out),encoding='utf-8')
