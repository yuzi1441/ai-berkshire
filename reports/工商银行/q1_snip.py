from pathlib import Path
text=(Path('sources')/'2026Q1_A.pdf.txt').read_text(encoding='utf-8')
for kw in ['主要会计数据','营业收入','利息净收入','归属于母公司股东的净利润','资产总计','客户贷款及垫款','负债合计','核心一级资本充足率','不良贷款率','拨备覆盖率','基本每股收益']:
    idx=text.find(kw)
    print('\n--',kw,idx,'--')
    if idx!=-1: print(text[idx:idx+2200])
