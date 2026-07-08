from pathlib import Path
import re, json
for year in [2022,2023,2024,2025]:
    p=Path(f'source_docs/pgdq/pg_{year}_annual.txt') if year<2025 else Path('source_docs/pgdq/pg_2025_annual.txt')
    text=p.read_text(encoding='utf-8', errors='ignore')
    lines=text.splitlines()
    terms=['经营活动现金流量净额','经营活动产生的现金流量净额','营业收入','归属于上市公司股东的净利润','现金分红','派发现金','年度利润分配','预计实现营业收入','公司实现营业收入','研发投入','应收账款净值','孙继强','张国跃','李俊涛','董事长','总经理']
    print('\n====',year,p.name,'====')
    for term in terms:
        hits=[]
        for i,l in enumerate(lines,1):
            if term in l:
                hits.append((i,l.strip()))
                if len(hits)>=3: break
        if hits:
            print('##',term)
            for i,l in hits: print(f'L{i}: {l}')
