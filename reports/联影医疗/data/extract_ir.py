import pdfplumber, pathlib
for f in ['ir2025apr.pdf','ir2025aug.pdf','ir2025oct.pdf','ir2026apr.pdf']:
    p=pathlib.Path('data')/f
    out=[]
    with pdfplumber.open(p) as pdf:
        for i,page in enumerate(pdf.pages):
            out.append(f'\n--- PAGE {i+1} ---\n'+(page.extract_text() or ''))
    pathlib.Path('data',f.replace('.pdf','.txt')).write_text('\n'.join(out),encoding='utf-8')
    print(f, len(out))
