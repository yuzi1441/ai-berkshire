import pdfplumber, pathlib, sys
p=pathlib.Path('data/united_imaging_2025_ar.pdf')
for start,end in [(37,44),(63,70),(76,83),(95,118),(121,129),(145,151),(155,159),(163,177),(187,203),(330,350),(358,366)]:
    out=[]
    with pdfplumber.open(p) as pdf:
        for n in range(start,end+1):
            txt=pdf.pages[n-1].extract_text() or ''
            out.append(f"\n--- PAGE {n} ---\n"+txt)
    pathlib.Path(f'data/pages_{start}_{end}.txt').write_text('\n'.join(out),encoding='utf-8')
    print(f'wrote pages_{start}_{end}.txt')
