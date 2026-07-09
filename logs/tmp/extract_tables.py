import pdfplumber, pathlib, json
base=pathlib.Path(r'E:\ai-berkshire\research\source_docs\jiangnan-chemical')
for pdf in sorted(base.glob('jiangnan-chemical-*-annual.pdf')):
    print('\n###', pdf.name)
    with pdfplumber.open(pdf) as p:
        for idx in range(6,9):
            page=p.pages[idx]
            print('--- page', idx+1)
            tables=page.extract_tables()
            for ti,table in enumerate(tables):
                print('TABLE', ti)
                for row in table[:20]:
                    print(' | '.join([(c or '').replace('\n',' ') for c in row]))
