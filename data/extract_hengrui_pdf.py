import pdfplumber, re, json
from pathlib import Path
pdf=Path('sources/恒瑞医药/恒瑞医药2025年年度报告-cninfo.pdf')
out=[]
with pdfplumber.open(pdf) as p:
    print('pages', len(p.pages))
    for i,page in enumerate(p.pages):
        text=page.extract_text() or ''
        if any(k in text for k in ['主要会计数据','营业收入','创新药','研发投入','分行业','分产品','现金流量表','资产负债表','产品管线','出海','销售费用','管理层讨论']):
            out.append((i+1,text[:4000]))
Path('data/hengrui_2025_selected_pages.txt').write_text('\n\n---PAGE---\n\n'.join([f'PAGE {i}\n{text}' for i,text in out]),encoding='utf-8')
print('selected', [i for i,_ in out[:80]])
