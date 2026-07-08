import pdfplumber
pdf='source_docs/pgdq/pg_2025_annual.pdf'
for pno in [73,74,75,76,77,78]:
    with pdfplumber.open(pdf) as p:
        text=p.pages[pno-1].extract_text() or ''
        print('\n==== PAGE',pno,'====')
        print(text[:5000])
