from pathlib import Path
base=Path('sources/联影医疗')
for fname in ['2025年报.pdf.txt','2026Q1.pdf.txt']:
    text=(base/fname).read_text(encoding='utf-8')
    print('\n====',fname,'====')
    pats=['营业收入','归属于上市公司股东的净利润','归属于上市公司股东的扣除非经常性损益的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','研发投入','资产总额','归属于上市公司股东的所有者权益','医疗设备','医疗IT','医学影像','收入构成','分产品','境内','境外','毛利率','销售费用','管理费用','研发费用','合同负债','存货','应收账款']
    for pat in pats:
        idx=text.find(pat)
        if idx>=0:
            s=text[max(0,idx-300):idx+900]
            print(f'\n--- {pat} @ {idx} ---')
            print(s[:1200])
