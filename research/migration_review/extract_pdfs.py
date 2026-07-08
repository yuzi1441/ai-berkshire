import pdfplumber, pathlib, re, json
src=pathlib.Path('reports/中国神华/sources')
for pdf in [src/'2026Q1.pdf', src/'2025Annual.pdf']:
    print('---',pdf, pdf.stat().st_size)
    pages=[]
    with pdfplumber.open(pdf) as p:
        print('pages',len(p.pages))
        for i,page in enumerate(p.pages,1):
            text=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            pages.append(f'--- page {i} ---\n{text}')
    out=pdf.with_suffix('.txt')
    out.write_text('\n'.join(pages),encoding='utf-8')
    print('wrote',out, out.stat().st_size)
    # find useful snippets
    text='\n'.join(pages)
    pats=['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','基本每股收益','资产总计','煤炭销售量','商品煤产量','售电量','铁路运输周转量','分行业','分部','主营业务']
    for pat in pats:
        m=re.search(pat,text)
        if m:
            print('PAT',pat,'pos',m.start(), text[max(0,m.start()-200):m.start()+500].replace('\n',' | ')[:800])
