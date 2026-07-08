import pdfplumber, pathlib, sys
pdf=pathlib.Path('_source/icbc_2025_annual_A.pdf')
for pg in [10,11,12,13,21,22,25,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,271,272,290]:
    with pdfplumber.open(pdf) as p:
        txt=p.pages[pg-1].extract_text(x_tolerance=1, y_tolerance=3) or ''
    print('\n'+'='*20+f' PAGE {pg} '+'='*20)
    print(txt[:4000])
