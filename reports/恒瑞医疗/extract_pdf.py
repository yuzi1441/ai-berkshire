from pypdf import PdfReader
from pathlib import Path
for pdf in ['sources/hengrui_2025_annual.pdf','sources/hengrui_2026_q1.pdf']:
    r=PdfReader(pdf)
    print('\nPDF', pdf, 'pages', len(r.pages))
    out=[]
    for i,p in enumerate(r.pages):
        try: txt=p.extract_text() or ''
        except Exception as e: txt='ERR '+repr(e)
        if any(k in txt for k in ['营业收入','归属于上市公司股东','研发','经营活动','总资产','创新药','主要会计数据','主营业务']):
            print('---page',i+1,'---')
            print(txt[:2500].replace('\n','\n'))
            out.append((i+1,txt))
    Path(pdf+'.txt').write_text('\n\n'.join(f'---PAGE {i}---\n{t}' for i,t in out), encoding='utf-8')