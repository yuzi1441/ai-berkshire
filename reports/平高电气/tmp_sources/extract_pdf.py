import pdfplumber, pathlib
for fname in ['pinggao_2026q1.pdf','pinggao_2025annual.pdf']:
    path=pathlib.Path('tmp_sources')/fname
    out=path.with_suffix('.txt')
    texts=[]
    with pdfplumber.open(path) as pdf:
        for i,p in enumerate(pdf.pages):
            txt=p.extract_text() or ''
            texts.append(f'\n--- page {i+1} ---\n'+txt)
    out.write_text('\n'.join(texts), encoding='utf-8')
    print(fname, 'pages', len(texts), 'chars', sum(map(len,texts)), 'out', out)
