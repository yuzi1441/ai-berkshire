import pdfplumber, pathlib
p=pathlib.Path('data/eastone_000682_raw/1225161855.pdf')
with pdfplumber.open(p) as doc:
    for pg in [32,33,34]:
        page=doc.pages[pg-1]
        print('\n---PAGE',pg,'TEXT---')
        print((page.extract_text() or '')[:3000])
        print('\n---TABLES---')
        for t in page.extract_tables() or []:
            for row in t[:20]: print(row)
            print('---')
