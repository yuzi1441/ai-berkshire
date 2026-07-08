from pathlib import Path
text=Path('sources/mindray_2025_annual.txt').read_text(encoding='utf-8')
# Extract around page 96 product table and page 23 geography
for start_pat in ['分行业 医疗器械行','体外诊断业务实现营业收入','生命信息与支持业务实现营业收入','医学影像业务实现营业收入','新兴业务实现营业收入','国际市场，报告期内，公司国际业务实现收入','国内市场，报告期内，公司国内业务实现收入','研发投入金额','研发人员数量','现金分红','公司2025年度利润分配预案']:
    idx=text.find(start_pat)
    print('\n###',start_pat,idx)
    if idx>=0:
        print(text[idx:idx+3000].replace('\n',' '))
