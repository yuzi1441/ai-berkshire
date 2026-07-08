import pdfplumber, pathlib
pdf=pathlib.Path('data/长江电力/长江电力2024年度环境、社会和治理（ESG）报告_1223421180.pdf')
keywords=['员工','培训','安全','客户','供应商','反腐','合规','投诉','满意','文化','人才','薪酬']
with pdfplumber.open(pdf) as p:
    print('pages', len(p.pages))
    for i,page in enumerate(p.pages,1):
        txt=page.extract_text() or ''
        if any(k in txt for k in keywords):
            for kw in keywords:
                if kw in txt:
                    idx=txt.find(kw); print('\nP',i,kw,txt[max(0,idx-300):idx+900].replace('\n',' ')[:1300]); break
