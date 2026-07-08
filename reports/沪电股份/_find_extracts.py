from pathlib import Path
for file in ['source_pdfs/hudian_2025_annual.pdf.extract.txt','source_pdfs/hudian_2026_q1.pdf.extract.txt']:
    text=Path(file).read_text(encoding='utf-8')
    print('===',file)
    for kw in ['主要会计数据和财务指标','归属于上市公司股东的净利润','营业收入','分季度主要财务指标','合并资产负债表','合并利润表','合并现金流量表','前五名客户','研发投入','经营活动产生的现金流量净额','加权平均净资产收益率']:
        idx=text.find(kw)
        print(kw, idx)
        if idx!=-1:
            print(text[max(0,idx-500):idx+1500].replace('\n','\n')[:2200])
            print('---')
