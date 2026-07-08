from pathlib import Path
for file in ['q1_text.txt','ar_text.txt']:
    txt=Path(file).read_text(encoding='utf-8')
    print('\n====',file,'====')
    for term in ['一、主要财务数据','合并资产负债表','合并利润表','合并现金流量表','主要财务指标','第四节 公司治理','分季度主要财务指标','现金分红','利润分配','应收账款','存货','资产负债率','营业收入构成','主营业务分析','费用']:
        pos=txt.find(term)
        if pos!=-1:
            print('\n--- term',term,'pos',pos,'---')
            print(txt[max(0,pos-500):pos+2500])
