from pathlib import Path
base=Path('reports/华明装备/sources')
text=(base/'sina_2025AR_11972985.html.text.txt').read_text(encoding='utf-8')
keywords=['分接开关','有载分接开关','无励磁分接开关','全球','国内','MR','德国MR','核心技术','竞争','壁垒','特高压','海外','电网投资','新能源','业绩驱动因素','风险','主要风险','行业格局','行业发展']
outs=[]
for kw in keywords:
    idxs=[]; start=0
    while True:
        idx=text.find(kw,start)
        if idx==-1: break
        idxs.append(idx); start=idx+len(kw)
        if len(idxs)>=5: break
    outs.append(f'### {kw} {idxs}')
    for idx in idxs[:3]:
        outs.append(text[max(0,idx-600):idx+1600])
        outs.append('---')
(base/'business_moat_snips.txt').write_text('\n'.join(outs),encoding='utf-8')
print((base/'business_moat_snips.txt').read_text(encoding='utf-8')[:20000])
