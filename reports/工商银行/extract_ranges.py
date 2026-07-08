import pdfplumber, pathlib, re
pdf=pathlib.Path('_source/icbc_2025_annual_A.pdf')
for start,end,name in [(52,61,'risk'),(63,75,'loans'),(167,178,'statements'),(272,274,'capital')]:
    with pdfplumber.open(pdf) as p:
        out=[]
        for pg in range(start,end+1):
            txt=p.pages[pg-1].extract_text(x_tolerance=1, y_tolerance=3) or ''
            out.append('\n'+'='*20+f' PAGE {pg} '+'='*20+'\n'+txt[:5000])
    pathlib.Path(f'_source/{name}_{start}_{end}.txt').write_text('\n'.join(out),encoding='utf-8')
    print(name, start,end)
