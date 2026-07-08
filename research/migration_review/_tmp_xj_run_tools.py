import json, subprocess, pathlib, math
q=json.loads(pathlib.Path('data/xj-electric/summary_000400.json').read_text(encoding='utf-8'))
price=q['quote']['tencent']['price']; shares=q['quote']['tencent']['shares_total']; mcap_yi=q['quote']['tencent']['market_cap_yi']
eps=q['基本每股收益']['20251231']; bvps=12150593337.07/shares; div=0.389; revps=q['营业总收入']['20251231']/shares
ocfps=2670382574.97/shares
print('inputs',price,shares,mcap_yi,eps,bvps,div,revps,ocfps)
cmds=[
 ['python','tools/financial_rigor.py','verify-market-cap','--price',str(price),'--shares',str(shares),'--reported',str(mcap_yi*1e8),'--currency','CNY'],
 ['python','tools/financial_rigor.py','verify-valuation','--price',str(price),'--eps',str(eps),'--bvps',str(bvps),'--fcf-per-share',str(ocfps),'--dividend',str(div),'--revenue-per-share',str(revps)],
 ['python','tools/financial_rigor.py','three-scenario','--price',str(price),'--eps',str(eps),'--shares',str(shares/1e8),'--growth','0.12','0.06','-0.02','--pe','22','18','13','--years','3','--currency','CNY'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2025营业收入','--values','{"年报":149.9190606624,"同花顺接口":149.9190606624,"东方财富指标":149.9190606624}','--unit','亿元'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2025归母净利润','--values','{"年报":11.6721000973,"同花顺接口":11.6721000973,"东方财富指标":11.6721000973}','--unit','亿元'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2026Q1营业收入','--values','{"一季报":23.7775158279,"同花顺接口":23.7775158279}','--unit','亿元'],
 ['python','tools/financial_rigor.py','cross-validate','--field','2026Q1归母净利润','--values','{"一季报":1.1104623014,"同花顺接口":1.1104623014}','--unit','亿元'],
]
out=[]
for c in cmds:
 print('\n$',' '.join(c))
 r=subprocess.run(c,capture_output=True,text=True,encoding='utf-8')
 print(r.stdout); print(r.stderr)
 out.append({'cmd':' '.join(c),'stdout':r.stdout,'stderr':r.stderr,'returncode':r.returncode})
pathlib.Path('data/xj-electric/valuation_tool_outputs.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
