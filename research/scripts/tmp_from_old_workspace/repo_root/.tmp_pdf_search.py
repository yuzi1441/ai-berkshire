import pdfplumber, re, pathlib, json
pdf=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources\siyuan_2025_annual.pdf')
keywords=['营业收入','主营业务','分行业','分产品','分地区','主要会计数据','研发投入','前五名客户','前五名供应商','董事长','管理层','股本','竞争','市场占有','应收账款','现金流','资产负债率','输配电','海外']
with pdfplumber.open(pdf) as p:
    print('pages',len(p.pages))
    hits={k:[] for k in keywords}
    for i,page in enumerate(p.pages,1):
        text=page.extract_text() or ''
        for k in keywords:
            if k in text:
                hits[k].append(i)
    for k,v in hits.items(): print(k,v[:20])
