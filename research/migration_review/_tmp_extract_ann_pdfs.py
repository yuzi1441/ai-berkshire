import pdfplumber, pathlib
for pdf in pathlib.Path('data/长江电力').glob('长江电力*.pdf'):
    print('\n===', pdf.name, '===')
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            print('\n---PAGE',i,'---')
            print(txt[:3500])
