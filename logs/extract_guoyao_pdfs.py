import pdfplumber, pathlib, re, json
src=pathlib.Path('research/source_docs/国药现代')
out=pathlib.Path('research/sources/国药现代'); out.mkdir(parents=True, exist_ok=True)
for pdf in src.glob('*.pdf'):
    text=[]
    with pdfplumber.open(str(pdf)) as p:
        for i,page in enumerate(p.pages):
            t=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            text.append(f'\n\n--- PAGE {i+1} ---\n'+t)
    path=out/(pdf.stem+'.txt')
    path.write_text('\n'.join(text), encoding='utf-8')
    print(pdf.name, 'pages', len(text), 'chars', sum(map(len,text)), '->', path)
