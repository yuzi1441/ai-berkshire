import pdfplumber, pathlib, re, json
base=pathlib.Path('reports/华明装备/sources')
files=['2025AR_11972985.pdf','2026Q1_12201904.pdf','2024AR_10862534.pdf']
for fn in files:
    path=base/fn
    out=base/(fn+'.txt')
    print('extract',path,path.exists(),path.stat().st_size if path.exists() else None)
    texts=[]
    with pdfplumber.open(path) as pdf:
        print('pages',len(pdf.pages))
        for i,p in enumerate(pdf.pages, start=1):
            try: txt=p.extract_text(x_tolerance=1, y_tolerance=3) or ''
            except Exception as e: txt='ERR '+repr(e)
            texts.append(f'\n\n===== PAGE {i} =====\n'+txt)
    out.write_text('\n'.join(texts),encoding='utf-8')
    print('wrote',out, out.stat().st_size)
    # find keyword pages
    alltxt='\n'.join(texts)
    for kw in ['营业收入构成','主营业务分析','分行业','分产品','归属于上市公司股东的净利润','经营活动产生的现金流量净额','研发投入','股本','董事','实际控制人','分红','境外', '数智电网']:
        pages=[]
        for m in re.finditer(re.escape(kw), alltxt):
            prev=alltxt.rfind('===== PAGE ',0,m.start())
            pg='?'
            if prev!=-1:
                mm=re.match(r'===== PAGE (\d+)', alltxt[prev+1:prev+30])
                if mm: pg=mm.group(1)
            pages.append(pg)
        if pages: print(' ',kw, sorted(set(pages))[:10])
