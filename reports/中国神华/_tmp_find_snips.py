from pathlib import Path
text=Path('_tmp_annual_pages_utf8.txt').read_text(encoding='utf-8')
for kw in ['合并现金流量表','货币资金','短期借款','长期借款','应付债券','合并资产负债表','主营业务分行业情况','2025 年主营业务分行业','利润总额 46,597','表5 分部信息','分部收入小计','近 5 年主要财务信息摘要']:
    print('\n###',kw)
    i=text.find(kw)
    print(i)
    if i!=-1: print(text[i-1000:i+3000])
