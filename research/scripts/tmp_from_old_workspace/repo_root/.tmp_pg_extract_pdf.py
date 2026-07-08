import pdfplumber, pathlib, re, json
base=pathlib.Path('sources/平高电气')
for fname in ['2025_annual.pdf','2026_q1.pdf','2024_annual.pdf']:
    p=base/fname
    print('---',fname,'---')
    with pdfplumber.open(p) as pdf:
        print('pages', len(pdf.pages))
        text='\n'.join((page.extract_text() or '') for page in pdf.pages)
    (base/(fname+'.txt')).write_text(text, encoding='utf-8')
    for pat in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','主营业务分行业', '主营业务分产品', '分行业', '营业成本', '毛利率', '研发投入', '基本每股收益', '总资产']:
        m=text.find(pat)
        print(pat, m)
        if m!=-1: print(text[m:m+800].replace('\n',' | ')[:800])
