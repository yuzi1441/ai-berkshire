import pdfplumber, pathlib
for name,pages in [('annual2025.pdf', range(1,311)), ('q1_2026.pdf', range(1,20))]:
    pdf=pathlib.Path('sources')/name
    out=pathlib.Path('sources')/(name+'.key.txt')
    texts=[]
    with pdfplumber.open(pdf) as p:
        print(name, len(p.pages))
        for i,page in enumerate(p.pages, start=1):
            txt=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            if any(k in txt for k in ['主要会计数据','分行业','分产品','营业收入','煤炭销售量','商品煤产量','发电量','经营活动产生的现金流量','合并利润表','合并资产负债表','合并现金流量表','一、主要财务数据']):
                texts.append(f'\n===== PAGE {i} =====\n'+txt[:9000])
    out.write_text('\n'.join(texts), encoding='utf-8')
    print(out, out.stat().st_size)
