import pdfplumber, pathlib
for pdf,out in [('sources/annual2025.pdf','_tmp_annual2025_full.txt'),('sources/q1_2026.pdf','_tmp_q1_2026_full.txt')]:
    parts=[]
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages,1):
            text=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            parts.append(f'\n===== PAGE {i} =====\n{text}')
    pathlib.Path(out).write_text('\n'.join(parts), encoding='utf-8')
    print(out, pathlib.Path(out).stat().st_size)
