import pdfplumber, re, os, pathlib, json
files={'2025AR':'sources/002028/2025AR_1225117829.pdf','2026Q1':'sources/002028/2026Q1_1225177123.pdf','2024AR':'sources/002028/2024AR_1223145398.pdf','2023AR':'sources/002028/2023AR_1219702367.pdf'}
os.makedirs('sources/002028/text', exist_ok=True)
keywords=['主要会计数据','营业收入','归属于上市公司股东','分行业','分产品','主营业务','核心竞争力','研发','现金流','前十名股东','管理层','董事','回购','利润分配','负债','在建工程','资本开支','海外','输配电','智能电网','互感器','开关','变压器']
for name,path in files.items():
    print('\n---',name,path,'---')
    with pdfplumber.open(path) as pdf:
        print('pages',len(pdf.pages))
        hits=[]
        # extract all text for q1 and first? maybe annual full can be slow but okay
        full=[]
        for i,p in enumerate(pdf.pages):
            txt=p.extract_text() or ''
            full.append(f'\n\n--- page {i+1} ---\n'+txt)
            if any(k in txt for k in keywords):
                hits.append(i+1)
        out=f'sources/002028/text/{name}.txt'
        open(out,'w',encoding='utf-8').write(''.join(full))
        print('saved',out,'hits first 80',hits[:80])
