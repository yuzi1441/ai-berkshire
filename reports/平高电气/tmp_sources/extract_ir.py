import pdfplumber, pathlib
path=pathlib.Path('tmp_sources/pinggao_2025_2026q1_ir.pdf')
texts=[]
with pdfplumber.open(path) as pdf:
    for i,p in enumerate(pdf.pages):
        texts.append(f'\n--- page {i+1} ---\n'+(p.extract_text() or ''))
out=path.with_suffix('.txt')
out.write_text('\n'.join(texts), encoding='utf-8')
print('pages',len(texts),'chars',sum(map(len,texts)))
