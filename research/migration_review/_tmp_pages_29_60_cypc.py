import pdfplumber, pathlib
pdf=pathlib.Path('data/长江电力/annual2025.pdf')
with pdfplumber.open(pdf) as p:
    for n in range(29,61):
        txt=p.pages[n-1].extract_text(x_tolerance=1, y_tolerance=3) or ''
        print('\n'+'='*20+' PAGE '+str(n)+' '+'='*20)
        print(txt[:5000])
