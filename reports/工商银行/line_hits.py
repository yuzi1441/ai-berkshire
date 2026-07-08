from pathlib import Path
lines=Path('annual_selected_pages.txt').read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines,1):
    if any(p in line for p in ['按行业划分的贷款', '房地产业', '个人住房贷款', '贷款质量五级分类', '按行业划分的不良', '关注类贷款', '逾期贷款', '重组贷款', '客户贷款及垫款减值准备']):
        print(i, line)
