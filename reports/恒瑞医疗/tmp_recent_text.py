from pathlib import Path
import pdfplumber, sys, re
sys.stdout.reconfigure(encoding='utf-8')
for p in sorted(Path('source_pdfs/cninfo_recent').glob('*.pdf')):
    with pdfplumber.open(str(p)) as pdf:
        txt='\n'.join(page.extract_text() or '' for page in pdf.pages)
    print('\n###',p.name)
    # print first 1200 chars after title
    print(txt[:1800].replace('\n',' ')[:1800])
