from pathlib import Path
import pdfplumber, re, json
for pdf in ['sifang_2026q1_xueqiu.pdf','sifang_2025_ar_cninfo.pdf']:
    out=Path(pdf).with_suffix('.txt')
    texts=[]
    with pdfplumber.open(pdf) as p:
        print(pdf, 'pages', len(p.pages))
        for i,page in enumerate(p.pages,1):
            txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            texts.append(f'\n\n--- PAGE {i} ---\n'+txt)
    out.write_text('\n'.join(texts), encoding='utf-8')
    print('wrote', out, out.stat().st_size)
