import pdfplumber
from pathlib import Path
for src,dst in [('四方股份-2026Q1-新浪.PDF','四方股份2026Q1_text.txt'),('_tmp_2025.pdf','四方股份2025annual_text.txt')]:
    texts=[]
    with pdfplumber.open(src) as pdf:
        for i,p in enumerate(pdf.pages,1):
            text=p.extract_text(x_tolerance=1, y_tolerance=3) or ''
            texts.append(f'\n\n--- PAGE {i} ---\n'+text)
    Path(dst).write_text('\n'.join(texts),encoding='utf-8')
    print(dst, len('\n'.join(texts)))
