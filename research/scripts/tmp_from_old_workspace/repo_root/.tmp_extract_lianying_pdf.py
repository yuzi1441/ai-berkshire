import pdfplumber, pathlib
for name in ['lianying_annual_20260429_1225233728.pdf','lianying_q1_20260429_1225233744.pdf']:
    p=pathlib.Path('sources/联影医疗')/name
    out=p.with_suffix(p.suffix+'.txt')
    print('extract', p)
    texts=[]
    with pdfplumber.open(p) as pdf:
        print('pages', len(pdf.pages))
        for i,page in enumerate(pdf.pages):
            t=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            texts.append(f'\n\n--- page {i+1} ---\n'+t)
    out.write_text('\n'.join(texts), encoding='utf-8')
    print(out, out.stat().st_size)
