import pathlib,re,sys
base=pathlib.Path('reports/华明装备/sources')
out=[]
for txtfile in ['2025AR_11972985.pdf.txt','2026Q1_12201904.pdf.txt','2024AR_10862534.pdf.txt']:
    text=(base/txtfile).read_text(encoding='utf-8',errors='ignore')
    out.append('\n==== '+txtfile+' ====')
    for kw in ['公司简介和主要财务指标','营业收入构成','占营业收入比重','主营业务分析','分行业','分产品','研发投入','现金流','普通股股份变动','前10名股东','股利分配','实际控制人','控股股东','境外销售','核心竞争力','经营情况讨论']:
        idx=text.find(kw)
        out.append(f'KW {kw} idx {idx}')
        if idx!=-1:
            out.append(text[idx:idx+2200].replace('\n\n','\n')[:2200])
            out.append('---')
(base/'key_snippets.txt').write_text('\n'.join(out),encoding='utf-8')
print('wrote',base/'key_snippets.txt')
