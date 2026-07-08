import pdfplumber, pathlib, re
pdf=pathlib.Path('data/长江电力/annual2025.pdf')
with pdfplumber.open(pdf) as p:
    for n in range(1,80):
        txt=p.pages[n-1].extract_text() or ''
        if any(k in txt for k in ['董事、监事、高级管理人员','公司治理','利润分配','股份变动','关联交易','前十名股东','现金分红','董事会成员']):
            print('\n---PAGE',n,'---')
            print(txt[:2500])
