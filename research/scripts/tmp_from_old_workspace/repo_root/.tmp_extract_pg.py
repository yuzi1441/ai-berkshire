import pdfplumber, pathlib, re, json
for pdf in ['source_docs/pgdq/pg_2025_annual.pdf','source_docs/pgdq/pg_2026_q1.pdf']:
    print('\n###', pdf)
    with pdfplumber.open(pdf) as p:
        print('pages', len(p.pages))
        needles=['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','总资产','归属于上市公司股东的净资产','货币资金','应收账款','存货','合同负债','短期借款','资产负债率','营业总收入','归属于上市公司股东的所有者权益']
        for i,page in enumerate(p.pages):
            text=page.extract_text() or ''
            if any(n in text for n in needles):
                print('\n--- page', i+1, '---')
                for line in text.splitlines():
                    if any(n in line for n in needles):
                        print(line[:300])
