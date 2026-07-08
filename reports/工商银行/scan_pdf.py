import pdfplumber, re, pathlib, json
pdf=pathlib.Path('_source/icbc_2025_annual_A.pdf')
keywords=['经营成果','营业收入','净利润','净利息收入','利息净收入','净息差','平均总资产回报率','加权平均净资产收益率','成本收入比','不良贷款率','拨备覆盖率','资本充足率','核心一级资本充足率','每股净资产','基本每股收益','现金分红']
with pdfplumber.open(pdf) as p:
    print('pages', len(p.pages))
    hits=[]
    for i,page in enumerate(p.pages):
        txt=page.extract_text() or ''
        for kw in keywords:
            if kw in txt:
                hits.append((i+1,kw, txt[:200].replace('\n',' | ')))
                break
    print('hits', len(hits))
    for h in hits[:80]: print(h)
