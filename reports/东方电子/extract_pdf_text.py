import pdfplumber, re, pathlib, json
base=pathlib.Path('cninfo_pdfs')
out=pathlib.Path('pdf_text'); out.mkdir(exist_ok=True)
for pdf in base.glob('*.PDF'):
    txt=[]
    with pdfplumber.open(pdf) as p:
        print(pdf.name, len(p.pages))
        for i,page in enumerate(p.pages):
            t=page.extract_text() or ''
            txt.append(f'\n---PAGE {i+1}---\n'+t)
    (out/(pdf.stem+'.txt')).write_text('\n'.join(txt),encoding='utf-8')
print(out.resolve())
