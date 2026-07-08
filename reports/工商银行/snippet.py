from pathlib import Path
for fn in ['2025AnnualReportA.pdf.txt','2026Q1_A.pdf.txt']:
    print('\n###',fn)
    text=(Path('sources')/fn).read_text(encoding='utf-8')
    for kw in ['财务数据','利息净收入','营业收入','净利润','每股收益','归属于母公司普通股股东的每股净资产','净利息收益率','不良贷款率','拨备覆盖率','核心一级资本充足率','主要会计数据','普通股股份总数','资本充足率']:
        idx=text.find(kw)
        if idx!=-1:
            print('\n--',kw,'--')
            print(text[idx:idx+1600])
