import pdfplumber, pathlib, re, json
base=pathlib.Path('research/source_docs/中航机载')
out=base/'extracted_text'; out.mkdir(exist_ok=True)
for pdf in base.glob('*.pdf'):
    texts=[]
    with pdfplumber.open(pdf) as p:
        print(pdf.name, 'pages', len(p.pages))
        for i,page in enumerate(p.pages):
            txt=page.extract_text() or ''
            texts.append(f'\n---PAGE {i+1}---\n'+txt)
    (out/(pdf.stem+'.txt')).write_text('\n'.join(texts), encoding='utf-8')
    print('chars', sum(map(len,texts)))