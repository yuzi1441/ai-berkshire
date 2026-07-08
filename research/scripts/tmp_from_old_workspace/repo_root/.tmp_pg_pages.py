import pdfplumber, pathlib, json
pdf='source_docs/pgdq/pg_2025_annual.pdf'
for pno in [17,18,19,20,72,73,74,153,154,155,58,59,60,61,62,94,95,96,179,180]:
    with pdfplumber.open(pdf) as p:
        if pno<=len(p.pages):
            page=p.pages[pno-1]
            print('\n==== PAGE', pno, '====')
            text=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            print(text[:2500])
            tables=page.extract_tables()
            print('tables', len(tables))
            for ti,t in enumerate(tables[:3]):
                print('TABLE',ti)
                for row in t[:10]: print(row)
