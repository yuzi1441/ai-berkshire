import pdfplumber, pathlib, re
pdf=pathlib.Path('data/长江电力/annual2025.pdf')
with pdfplumber.open(pdf) as p:
    for n in [6,7,89,90,91,92,93,94,95,96,97,193,194,195]:
        txt=p.pages[n-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
        print('\n===== PAGE',n,'=====')
        print(txt[:4000])
