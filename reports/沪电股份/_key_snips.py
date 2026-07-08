from pathlib import Path
for file in ['source_pdfs/hudian_2025_annual.pdf.selected.txt','source_pdfs/hudian_2026_q1.pdf.selected.txt']:
    text=Path(file).read_text(encoding='utf-8')
    print('===',file)
    for kw in ['货币资金','短期借款','长期借款','资产合计','负债合计','所有者权益合计','营业总收入','营业收入','营业总成本','研发费用','净利润','经营活动产生的现金流量净额','购建固定资产','现金及现金等价物净增加额','存货','应收账款','研发投入金额','资本化研发投入','董事、监事和高级管理人员持股变动','吴礼淦','陈梅芳','吴传彬','薪酬','分配预案']:
        idx=text.find(kw)
        if idx!=-1:
            print('\n---',kw,'idx',idx,'---')
            print(text[max(0,idx-500):idx+1200])
