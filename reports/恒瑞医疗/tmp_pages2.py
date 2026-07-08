from pathlib import Path
import pdfplumber, sys
sys.stdout.reconfigure(encoding='utf-8')
p=Path('source_pdfs/hengrui_2025_annual.pdf')
with pdfplumber.open(str(p)) as pdf:
    for pg in [6,12,13,24,25,26,27,28,29,30,31,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95]:
        txt=pdf.pages[pg-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
        print(f'\n===== PAGE {pg} =====')
        print(txt[:4500])
