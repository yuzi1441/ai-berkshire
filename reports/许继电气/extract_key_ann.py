from pathlib import Path
import pdfplumber, glob
for pdf in glob.glob('*.pdf')+glob.glob('*.PDF'):
    if pdf in ['1225096177.PDF','1225096189_2026Q1.PDF']: continue
    out=Path(pdf).with_suffix('.txt')
    try:
        parts=[]
        with pdfplumber.open(pdf) as p:
            for i,page in enumerate(p.pages,1):
                parts.append(f'\n--- PAGE {i} ---\n'+(page.extract_text() or ''))
        out.write_text('\n'.join(parts),encoding='utf-8')
        print(pdf, len(parts), 'pages')
    except Exception as e:
        print('ERR',pdf,e)