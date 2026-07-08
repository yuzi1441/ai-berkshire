import pdfplumber, pathlib, re, json, pandas as pd
src=pathlib.Path('sources/002270')
files=['2026Q1_1225181771.pdf','2025AR_1224986242.pdf','2025-10-27_1224737267_2025年三季度报告.pdf','2025-08-08_1224425948_2025年半年度报告.pdf','2024AR_1223055875.pdf','2023AR_1219567826.pdf']
out=pathlib.Path('data/huaming_002270/pdf_text'); out.mkdir(parents=True, exist_ok=True)
for f in files:
    path=src/f
    if not path.exists(): print('missing',f); continue
    print('\n---',f,path.stat().st_size,'---')
    texts=[]
    with pdfplumber.open(path) as pdf:
        print('pages',len(pdf.pages))
        for i,p in enumerate(pdf.pages):
            txt=p.extract_text(x_tolerance=1,y_tolerance=3) or ''
            texts.append(f'\n\n--- PAGE {i+1} ---\n'+txt)
    text=''.join(texts)
    (out/(f+'.txt')).write_text(text,encoding='utf-8')
    for pat in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','分产品','主营业务','关联交易','或有事项','股份支付','存货','应收账款','合同负债','毛利率','承诺']:
        idx=text.find(pat)
        if idx>=0:
            print('PAT',pat,'@',idx, text[idx:idx+300].replace('\n',' | '))