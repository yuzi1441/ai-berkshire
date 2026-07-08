from pathlib import Path
text=Path('sources/平高电气/2025_annual.pdf.txt').read_text(encoding='utf-8')
terms=['公司主要业务','经营情况讨论与分析','特高压','高压板块','配网板块','国际板块','运维检修','市场占有率','行业格局','竞争格局','核心竞争力','研发投入','母线','组合电器','断路器','隔离开关','海外','国网','南方电网','中国电气装备','董事长','总经理']
for term in terms:
    print('\n###',term)
    start=0; count=0
    while True:
        i=text.find(term,start)
        if i<0 or count>=3: break
        print('--- idx',i,'---')
        print(text[max(0,i-350):i+1000].replace('\n',' | ')[:1350])
        start=i+len(term); count+=1
