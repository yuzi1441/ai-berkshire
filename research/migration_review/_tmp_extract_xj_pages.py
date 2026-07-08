import pdfplumber, pathlib, re
for file in ['xj_2025_annual.pdf','xj_2026_q1.pdf']:
    p=pathlib.Path('source_docs/xj-electric')/file
    print('FILE', file)
    with pdfplumber.open(p) as pdf:
        print('pages', len(pdf.pages))
        for i in [0,1,2,3,4,5,6,7,8,9,10,20,30,40,50,60,70,80,90,100,110,120,130,140,150,160,170,180,190,200,210,220]:
            if i < len(pdf.pages):
                text = pdf.pages[i].extract_text() or ''
                if any(term in text for term in ['营业收入','归属于上市公司股东','分行业','分产品','主要会计数据','研发投入','前十名股东','主营业务','现金流量']):
                    print('\n--- page', i+1, '---')
                    print(text[:1500])
