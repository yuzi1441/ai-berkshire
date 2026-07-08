import pdfplumber, re, json, pathlib
pdf='source_docs/pgdq/pg_2025_annual.pdf'
with pdfplumber.open(pdf) as p:
    for pno in [6,7,72,73,74,75,76,77,78,79,80,81,82,83,153,154,155,156,160,161,193]:
        page=p.pages[pno-1]
        print('\n==== PAGE',pno,'====')
        text=page.extract_text() or ''
        print(text[:3500])
