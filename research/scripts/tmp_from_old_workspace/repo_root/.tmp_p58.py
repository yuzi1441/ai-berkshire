import pdfplumber, pathlib
p=pathlib.Path('data/eastone_000682_raw/1225161855.pdf')
with pdfplumber.open(p) as doc:
    for pg in [58,59,60]:
        print('\n---PAGE',pg,'---')
        print((doc.pages[pg-1].extract_text() or '')[:3500])
