from pathlib import Path
text=Path('sources/工商银行/ICBC-2026Q1.pdf.full.txt').read_text(encoding='utf-8')
for pat in ['客户贷款及垫款总额','投资 179,','客户存款','股东权益合计','不良贷款余额','核心一级资本充足率','本行于 2026 年 2 月','二级资本债券']:
    print('\n===',pat,'===')
    idx=text.find(pat)
    print(idx)
    print(text[max(0,idx-500):idx+1000].replace('\n',' '))
print('\n--- annual snippets ---')
text2=Path('sources/工商银行/ICBC-2025AnnualReportA.pdf.full.txt').read_text(encoding='utf-8')
for pat in ['财务数据（续）','营业收入 838,270','平均总资产回报率','投向制造业','科技创新','普惠','客户贷款及垫款总额','房地产','个人住房贷款','不良贷款率 1.31','利率']:
    print('\n===',pat,'===')
    idx=text2.find(pat)
    print(idx)
    print(text2[max(0,idx-500):idx+1200].replace('\n',' '))