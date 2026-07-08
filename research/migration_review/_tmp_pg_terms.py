from pathlib import Path
text=Path('source_docs/pgdq/pg_2025_annual.txt').read_text(encoding='utf-8')
lines=text.splitlines()
terms=['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','2026年经营计划','126-136','孙继强','张国跃','沈志翔','任职情况','薪酬总额','平高集团有限公司','中国电气装备集团有限公司','承诺将按照','五年内','关联交易','利润分配预案','10股派发现金股利','研发投入','新产品','国际市场','董事会会议','股权激励计划','应收账款','存货','经营计划','经营目标']
out=[]
for term in terms:
    out.append(f'\n### {term}')
    count=0
    for i,l in enumerate(lines,1):
        if term in l:
            out.append(f'L{i}: {l}')
            count+=1
            if count>=20: break
Path('source_docs/pgdq/term_hits_management.txt').write_text('\n'.join(out), encoding='utf-8')
print('ok')
