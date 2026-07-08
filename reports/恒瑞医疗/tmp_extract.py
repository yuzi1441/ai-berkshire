from pathlib import Path
import PyPDF2, re
paths=[Path('source_pdfs/hengrui_2025_annual.pdf'), Path('source_pdfs/hengrui_2026_q1.pdf')]+list(Path('source_pdfs/cninfo_recent').glob('*.pdf'))
for p in paths:
    try:
        reader=PyPDF2.PdfReader(str(p))
        text='\n'.join(page.extract_text() or '' for page in reader.pages[:5])
    except Exception as e:
        text=f'ERR {e}'
    print('\n---',p.name,'pages',len(reader.pages) if 'reader' in locals() else '?')
    print(text[:2000].replace('\n',' ')[:2000])
