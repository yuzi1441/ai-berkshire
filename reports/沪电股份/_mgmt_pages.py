from pathlib import Path
import pdfplumber
fname='source_pdfs/hudian_2025_annual.pdf'
with pdfplumber.open(fname) as pdf:
    pages=[]
    for n in range(35,62):
        pages.append(f'---page {n}---\n'+(pdf.pages[n-1].extract_text(x_tolerance=1,y_tolerance=3) or ''))
Path('source_pdfs/hudian_2025_annual_pages35_61.txt').write_text('\n\n'.join(pages),encoding='utf-8')
print('done')
