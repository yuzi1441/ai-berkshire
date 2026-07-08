import pdfplumber, pathlib, re, json
p=pathlib.Path('source_docs/xj-electric/xj_2025_annual.pdf')
terms=['主要业务','主营业务','分行业','分产品','分地区','收入构成','销售量','生产量','库存量','研发投入','现金及现金等价物','货币资金','前十名股东','控股股东','实际控制人','董事','高级管理人员','股本','利润分配','应收账款','存货','毛利率','资产负债率','竞争','市场','特高压','智能变配电','智能中压','智能电表','电动汽车','新能源']
with pdfplumber.open(p) as pdf:
    for i,page in enumerate(pdf.pages):
        text=page.extract_text() or ''
        hits=[t for t in terms if t in text]
        if hits:
            print(f'PAGE {i+1} hits={hits[:8]}')
            # print lines containing terms
            lines=text.splitlines()
            for line in lines:
                if any(t in line for t in terms):
                    print(' ', line[:220])
            print()
