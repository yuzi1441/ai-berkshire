from pathlib import Path
import pdfplumber
for fname in ['source_pdfs/hudian_2025_annual.pdf','source_pdfs/hudian_2026_q1.pdf']:
    with pdfplumber.open(fname) as pdf:
        pages=[]
        for n in ([7,8,20,21,22,23,24,25,26,27,30,54,57,62,63,80,81,83,84,85,86,87,88,89,90,97,102,103,104,105,106,110,116,118,121,125,126,127,132,133,134,135,136,137,138,139,140,141,142,143,144,145,146,147,148,149,150,151,152,153,184,185,186,187,188,189] if 'annual' in fname else [1,2,3,4,5,6,7,8]):
            if n<=len(pdf.pages):
                pages.append(f'---page {n}---\n'+(pdf.pages[n-1].extract_text(x_tolerance=1, y_tolerance=3) or ''))
    Path(fname+'.selected.txt').write_text('\n\n'.join(pages),encoding='utf-8')
    print(fname, 'written')
