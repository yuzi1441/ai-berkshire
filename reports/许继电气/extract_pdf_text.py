from pathlib import Path
import pdfplumber
for pdf,out in [('1225096177.PDF','xj_2025_annual_pdftext.txt'),('1225096189_2026Q1.PDF','xj_2026q1_pdftext.txt')]:
    parts=[]
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            parts.append(f'\n\n--- PAGE {i} ---\n{txt}')
    Path(out).write_text('\n'.join(parts),encoding='utf-8')
    print(pdf, len(parts), 'pages', Path(out).stat().st_size)