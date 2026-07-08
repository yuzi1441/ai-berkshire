from pathlib import Path
import re
for name in ['2025AR','2026Q1','2024AR','2023AR']:
    text=Path(f'sources/002028/text/{name}.txt').read_text(encoding='utf-8')
    print('\n===',name,'===')
    for pat in ['主要会计数据和财务指标','非经常性损益','分行业','分产品','现金流量表','前十名股东','核心竞争力','研发投入','利润分配','回购','主营业务','资产负债表','营业收入']:
        m=re.search(pat,text)
        print(pat, m.start() if m else None)
    # print excerpts around key headings
    for pat in ['主要会计数据和财务指标','分行业','分产品','核心竞争力','前十名股东','利润分配','2026年第一季度报告'][:]:
        m=re.search(pat,text)
        if m:
            s=max(0,m.start()-600); e=min(len(text),m.start()+2200)
            print('\n---excerpt',pat,'---')
            print(text[s:e].replace('\n',' ')[:2800])
