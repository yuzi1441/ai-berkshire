from pathlib import Path
import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')
p=Path('source_pdfs/hengrui_2025_annual.pdf')
with pdfplumber.open(str(p)) as pdf:
    for pg in [8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60]:
        txt=pdf.pages[pg-1].extract_text() or ''
        print(f'\n===== PAGE {pg} =====')
        print(txt[:3500])
