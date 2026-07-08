import pdfplumber, re, pathlib
pdf=pathlib.Path('sources/annual2025.pdf')
with pdfplumber.open(pdf) as p:
    for i,page in enumerate(p.pages, start=1):
        txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
        if any(k in txt for k in ['利润分配', '每 10 股', '每10股', '现金红利', '派发现金']):
            print('\n===== PAGE', i, '=====')
            print(txt[:6000])
