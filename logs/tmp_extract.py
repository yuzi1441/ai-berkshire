from pathlib import Path
pdf=Path('research/source_docs/国药现代/国药现代-2025年度报告-cninfo-1225037769.PDF')
out=pdf.with_suffix('.txt')
try:
    import pypdf
    reader=pypdf.PdfReader(str(pdf))
    texts=[]
    for i,p in enumerate(reader.pages):
        t=p.extract_text() or ''
        texts.append(f'\n--- page {i+1} ---\n'+t)
    out.write_text('\n'.join(texts), encoding='utf-8')
    print('pages', len(reader.pages), 'chars', out.stat().st_size, out.resolve())
except Exception as e:
    print('ERR', type(e), e)
