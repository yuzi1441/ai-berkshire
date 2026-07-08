from pathlib import Path
lines=Path('四方股份2026Q1_text.txt').read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines,1):
    if any(k in line for k in ['营业收入','营业成本','销售费用','研发费用','合并利润表','主要会计数据']):
        print(i, line)
