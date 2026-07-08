import pdfplumber, pathlib, re, json
base=pathlib.Path('sources')/'东方电子'
for pdf in base.glob('*.pdf'):
    print('PDF', pdf, pdf.stat().st_size)
    with pdfplumber.open(pdf) as p:
        print('pages', len(p.pages))
        text='\n'.join(page.extract_text() or '' for page in p.pages[:5])
        print(text[:3000])
        print('---tables first pages---')
        for i,page in enumerate(p.pages[:3]):
            tables=page.extract_tables()
            print('page',i+1,'tables',len(tables))
            for t in tables[:2]:
                for row in t[:5]: print(row)
                print('---')
        print('====')