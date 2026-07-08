import pdfplumber, pathlib, re, json
pdfs = [pathlib.Path('data/长江电力/annual2025.pdf'), pathlib.Path('data/长江电力/q1_2026.pdf'), pathlib.Path('data/长江电力/annual2024.pdf')]
keywords = ['董事长','总经理','高级管理人员','刘伟平','刘海波','张传红','薪酬','关联交易','利润分配','现金分红','承诺','股东','三峡集团','资本开支','投资','金沙江','乌白资产','收购','回购']
for pdf in pdfs:
    print('\n===', pdf, '===')
    with pdfplumber.open(pdf) as p:
        print('pages', len(p.pages))
        hits=[]
        for i,page in enumerate(p.pages, start=1):
            text=page.extract_text() or ''
            for kw in keywords:
                if kw in text:
                    idx=text.find(kw)
                    snip=text[max(0,idx-80):idx+220].replace('\n',' ')
                    hits.append((i,kw,snip))
                    break
        for h in hits[:80]:
            print(f'P{h[0]} {h[1]}: {h[2]}')
