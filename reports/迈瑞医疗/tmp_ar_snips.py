from pathlib import Path
text=Path('ar_text.txt').read_text(encoding='utf-8')
terms=['第二节 公司简介和主要财务指标','主要会计数据和财务指标','八、分季度主要财务指标','三、主营业务分析','2、收入与成本','营业收入构成','公司主营业务数据统计口径','5、现金流','资产及负债状况分析','第十节 财务报告','合并资产负债表','合并利润表','合并现金流量表','利润分配预案','现金分红']
for term in terms:
    pos=text.find(term)
    print(term,pos)
    if pos!=-1:
        print(text[pos:pos+5000])
        print('\n---END---\n')
