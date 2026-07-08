from pathlib import Path
try:
    import fitz
except Exception as e:
    print('no fitz',e); raise
pdf='source_docs/pgdq/pg_2025_annual.pdf'
doc=fitz.open(pdf)
texts=[]
for i,p in enumerate(doc,1):
    texts.append(f'\n\n--- page {i} ---\n'+p.get_text('text'))
Path('source_docs/pgdq/pg_2025_annual_fitz.txt').write_text('\n'.join(texts),encoding='utf-8')
print('pages',len(doc),'size',Path('source_docs/pgdq/pg_2025_annual_fitz.txt').stat().st_size)
