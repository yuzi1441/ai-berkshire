import pdfplumber, pathlib
for pdf in ['sources/600900_dividend_plan_cypc.pdf','sources/600900_esg_cypc_guess.pdf']:
    print('\nPDF',pdf)
    with pdfplumber.open(pdf) as p:
        print('pages',len(p.pages))
        terms=['现金分红','70%','80%','2026','2030','清洁能源','减排','发电量','客户','社会','电网','能源保供','梯级']
        hits={t:[] for t in terms}
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text() or ''
            for t in terms:
                if t in txt and len(hits[t])<5: hits[t].append(i)
        print(hits)
        for i in range(1,min(len(p.pages),8)+1):
            txt=p.pages[i-1].extract_text() or ''
            print(f'---PAGE {i}---')
            print(txt[:1800])