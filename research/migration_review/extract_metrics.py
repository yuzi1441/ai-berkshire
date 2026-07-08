from pathlib import Path
import re, json
base=Path('reports/中国神华/sources')
for name in ['2026Q1','2025Annual']:
    text=(base/f'{name}.txt').read_text(encoding='utf-8')
    print('\n====',name,'====')
    pats=['营业收入','利润总额','归属于上市公司股东的净利润','归属于上市公司股东的扣除非经常','经营活动产生的现金流量净额','购买商品、接受劳务支付的现金','购建固定资产','取得借款收到的现金','资产总计','负债合计','商品煤产量','煤炭销售量','总售电量','自有铁路运输周转量','每股股利','现金红利']
    for pat in pats:
        print('\n--',pat,'--')
        for m in re.finditer(pat,text):
            s=text[max(0,m.start()-350):m.start()+900]
            print(s.replace('\n',' | ')[:1300])
            break
# page extracts around annual pages 16-30, q1 pages 1,8-9,14-17
for src, ranges in [('2026Q1',[(1,3),(8,17)]),('2025Annual',[(15,45),(128,148),(176,185),(252,263)])]:
    text=(base/f'{src}.txt').read_text(encoding='utf-8')
    chunks=text.split('--- page ')
    out=[]
    for rng in ranges:
        for c in chunks:
            try: n=int(c.split(' ---',1)[0].strip())
            except: continue
            if rng[0]<=n<=rng[1]: out.append('--- page '+c)
    p=base/f'{src}_selected_pages.txt'; p.write_text('\n'.join(out),encoding='utf-8'); print('wrote',p,p.stat().st_size)
