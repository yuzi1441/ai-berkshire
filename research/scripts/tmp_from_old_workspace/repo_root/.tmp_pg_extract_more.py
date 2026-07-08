import pdfplumber, pathlib, re, pandas as pd, json, math
base=pathlib.Path('sources/平高电气')
files=['2025_annual.pdf','2024_annual_full.pdf','2023_annual.pdf','2022_annual.pdf','2021_annual.pdf','2026_q1.pdf']
for fname in files:
    p=base/fname
    txtp=base/(fname+'.txt')
    if not txtp.exists() or txtp.stat().st_size<1000:
        with pdfplumber.open(p) as pdf:
            text='\n'.join((page.extract_text() or '') for page in pdf.pages)
        txtp.write_text(text,encoding='utf-8')
    else:
        text=txtp.read_text(encoding='utf-8')
    print('\n---',fname,'len',len(text),'---')
    for term in ['主要会计数据', '营业收入', '期末总股本', '分季度', '主营业务分产品情况', '研发投入', '前十名股东', '重要会计数据']:
        idx=text.find(term)
        print(term, idx)
        if idx>=0:
            print(text[idx:idx+1200].replace('\n',' | ')[:1200])
