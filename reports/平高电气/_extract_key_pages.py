import pdfplumber, re, json
from pathlib import Path
base=Path('_sources')
for pdf in base.glob('*.pdf'):
    txt=[]
    with pdfplumber.open(pdf) as p:
        print(pdf.name, 'pages', len(p.pages))
        for i,page in enumerate(p.pages):
            t=page.extract_text() or ''
            if any(k in t for k in ['主要会计数据', '营业收入', '分行业', '经营活动产生的现金流量净额', '合同负债', '应收账款', '毛利率', '基本每股收益']):
                print('--- page', i+1)
                lines=[ln for ln in t.splitlines() if any(k in ln for k in ['营业收入','归属于上市公司股东的净利润','归属于上市公司股东的扣除非经常性损益的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','总资产','归属于上市公司股东的所有者权益','分行业','分产品','输变电','营业成本','毛利率','合同负债','应收账款','存货','资产负债率'])]
                print('\n'.join(lines[:80]))
