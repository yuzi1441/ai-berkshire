from pathlib import Path
text=Path('sources/mindray_2025_annual.txt').read_text(encoding='utf-8')
for pat in ['主要会计数据和财务指标','营业收入','归属于上市公司股东的净利润','分行业','分产品','分地区','研发投入','现金分红','利润分配','经营活动产生的现金流量净额','货币资金','应收账款','存货','商誉','管理层讨论与分析','2026年全年公司国内业务']:
    idx=text.find(pat)
    print('\nPAT',pat,'IDX',idx)
    if idx>=0:
        print(text[max(0,idx-500):idx+2500].replace('\n',' ')[:3000])
