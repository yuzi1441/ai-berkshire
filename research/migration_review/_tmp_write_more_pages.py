import pdfplumber, pathlib
pdf=pathlib.Path('data/长江电力/annual2025.pdf')
for a,b in [(9,15),(18,28),(45,52),(56,60),(197,209),(222,231)]:
    out=[]
    with pdfplumber.open(pdf) as p:
        for n in range(a,b+1):
            txt=p.pages[n-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
            out.append(f'\n===== PAGE {n} =====\n{txt}')
    path=pathlib.Path(f'data/长江电力/pages_{a}_{b}.txt')
    path.write_text('\n'.join(out), encoding='utf-8')
    print(path, path.stat().st_size)
