from pathlib import Path
import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')
p=Path('source_pdfs/hengrui_2026_q1.pdf')
with pdfplumber.open(str(p)) as pdf:
    for i,page in enumerate(pdf.pages,1):
        txt=page.extract_text() or ''
        print(f'\n===== Q1 PAGE {i} =====')
        print(txt[:3000])
