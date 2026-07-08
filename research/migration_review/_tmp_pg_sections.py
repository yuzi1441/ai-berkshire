from pathlib import Path
text=Path('source_docs/pgdq/pg_2025_annual.txt').read_text(encoding='utf-8')
terms=['一、经营情况讨论与分析','经营计划','公司未来发展的讨论与分析','报告期内主要经营情况','董事、高级管理人员薪酬情况','现任及报告期内离任董事和高级管理人员持股变动及薪酬情况','普通股股东数量及前十名股东持股情况表','控股股东及实际控制人情况','关联交易情况','承诺事项履行情况','利润分配或资本公积金转增预案','公司治理相关情况说明','股权激励计划','募集资金','现金分红']
for term in terms:
    print('\n###', term)
    idx=text.find(term)
    print('idx', idx)
    if idx!=-1:
        snip=text[max(0,idx-1500):idx+3500]
        print(snip[:5000])
