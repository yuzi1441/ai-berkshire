import pdfplumber, pathlib, re
base=pathlib.Path('sources/长江电力')
for fname in ['annual2025.pdf','q1_2026.pdf']:
    p=base/fname
    txt=[]
    with pdfplumber.open(p) as pdf:
        print(fname,'pages',len(pdf.pages))
        for i,page in enumerate(pdf.pages):
            t=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            txt.append(f'\n---PAGE {i+1}---\n'+t)
    out=base/(fname+'.txt')
    out.write_text('\n'.join(txt),encoding='utf-8')
    print('wrote',out, out.stat().st_size)
    text='\n'.join(txt)
    for term in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','加权平均净资产收益率','基本每股收益','资产总计','负债合计','现金分红','每10股','装机容量','乌东德','白鹤滩','毛利率']:
        idx=text.find(term)
        print(term, idx, text[idx-80:idx+220].replace('\n',' ') if idx>=0 else '')
