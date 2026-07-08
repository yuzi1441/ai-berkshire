from pathlib import Path
text=Path('sources/思源电气/q1_text.txt').read_text(encoding='utf-8')
for kw in ['一、主要财务数据','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','合并利润表','五、净利润','归属于母公司所有者的净利润','合并现金流量表','经营活动现金流入小计','经营活动产生的现金流量净额']:
    idx=text.find(kw)
    print('\nKW',kw,idx)
    if idx>=0: print(text[idx:idx+2000])
