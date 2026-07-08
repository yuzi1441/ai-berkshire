from pathlib import Path
import pdfplumber, re, sys, json
sys.stdout.reconfigure(encoding='utf-8')
for p in [Path('source_pdfs/hengrui_2025_annual.pdf'), Path('source_pdfs/hengrui_2026_q1.pdf')]:
    print('\n---',p.name)
    with pdfplumber.open(str(p)) as pdf:
        print('pages',len(pdf.pages))
        txt='\n'.join(page.extract_text() or '' for page in pdf.pages[:12])
        print(txt[:3000])
