import pdfplumber, pathlib, re, json, pandas as pd
src=pathlib.Path('sources/002270')
files=['2025-10-27_1224737267_2025年三季度报告.pdf','2025-08-08_1224425948_2025年半年度报告.pdf']
out=pathlib.Path('data/huaming_002270/pdf_text_tables'); out.mkdir(parents=True, exist_ok=True)
for f in files:
    path=src/f
    print('\n---',f,'---')
    with pdfplumber.open(path) as pdf:
        print('pages',len(pdf.pages))
        for i,p in enumerate(pdf.pages[:8]):
            txt=p.extract_text() or ''
            if any(k in txt for k in ['主要会计数据','营业收入','经营情况说明','分产品','营业收入构成']):
                print('\nPAGE',i+1)
                print(txt[:2500])
