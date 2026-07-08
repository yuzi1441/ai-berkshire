import pdfplumber
for pdf in ['source_docs/pgdq/pg_2026_q1.pdf']:
    with pdfplumber.open(pdf) as p:
        for pno in range(1,len(p.pages)+1):
            text=p.pages[pno-1].extract_text() or ''
            print('\n==== PAGE',pno,'====')
            print(text[:4000])
