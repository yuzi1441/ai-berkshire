import pathlib, re
base=pathlib.Path('reports/华明装备/sources')
for fn in ['2025AR_11972985.pdf.txt','2026Q1_12201904.pdf.txt','2024AR_10862534.pdf.txt']:
    text=(base/fn).read_text(encoding='utf-8',errors='ignore')
    try:
        fixed=text.encode('latin1','ignore').decode('utf-8','ignore')
    except Exception as e:
        print('fix err',fn,e); fixed=text
    out=base/(fn.replace('.txt','.fixed.txt'))
    out.write_text(fixed,encoding='utf-8')
    print('wrote',out,out.stat().st_size, fixed[:50].replace('\n',' '))
# snippets repaired
out=[]
for txtfile in ['2025AR_11972985.pdf.fixed.txt','2026Q1_12201904.pdf.fixed.txt','2024AR_10862534.pdf.fixed.txt']:
    text=(base/txtfile).read_text(encoding='utf-8',errors='ignore')
    out.append('\n==== '+txtfile+' ====')
    for kw in ['公司简介和主要财务指标','营业收入构成','占营业收入比重','主营业务分析','分行业','分产品','研发投入','现金流','普通股股份变动','前10名股东','股利分配','实际控制人','控股股东','境外销售','核心竞争力','经营情况讨论', '未来发展展望', '分接开关']:
        idx=text.find(kw)
        out.append(f'KW {kw} idx {idx}')
        if idx!=-1:
            out.append(text[idx:idx+3000].replace('\n\n','\n')[:3000])
            out.append('---')
(base/'key_snippets_fixed.txt').write_text('\n'.join(out),encoding='utf-8')
print('snips wrote')
