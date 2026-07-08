from decimal import Decimal, getcontext
getcontext().prec=28
# official annual data RMB yuan
rows={
 2021:{'rev':Decimal('9273310045.93'),'cost':Decimal('8001252109.90'),'net':Decimal('70774235.93'),'ocf':Decimal('1197783890.57'),'capex':Decimal('99384417.82'),'roe':Decimal('0.78')},
 2022:{'rev':Decimal('9274276019.30'),'cost':Decimal('7642983821.96'),'net':Decimal('212095564.31'),'ocf':Decimal('1396965090.43'),'capex':Decimal('69418927.60'),'roe':Decimal('2.30')},
 2023:{'rev':Decimal('11077000052.98'),'cost':Decimal('8708439829.51'),'net':Decimal('815714321.31'),'ocf':Decimal('2503949235.68'),'capex':Decimal('438885114.67'),'roe':Decimal('8.43')},
 2024:{'rev':Decimal('12401611323.40'),'cost':Decimal('9629133063.43'),'net':Decimal('1023171146.73'),'ocf':Decimal('3008156518.31'),'capex':Decimal('133827871.39'),'roe':Decimal('9.98')},
 2025:{'rev':Decimal('12516931784.56'),'cost':Decimal('9523386172.29'),'net':Decimal('1119833030.96'),'ocf':Decimal('810660127.91'),'capex':Decimal('299150556.76'),'roe':Decimal('10.28')},
}
for y,r in rows.items():
 r['gross_margin']=(r['rev']-r['cost'])/r['rev']*100
 r['fcf']=r['ocf']-r['capex']
 r['fcf_net']=(r['fcf']/r['net']*100) if r['net'] else None
print('year rev_bn net_bn roe gross_margin ocf_bn capex_bn fcf_bn fcf/net')
for y,r in rows.items():
 print(y, f"{r['rev']/Decimal(1e8):.2f}", f"{r['net']/Decimal(1e8):.2f}", f"{r['roe']:.2f}%", f"{r['gross_margin']:.2f}%", f"{r['ocf']/Decimal(1e8):.2f}", f"{r['capex']/Decimal(1e8):.2f}", f"{r['fcf']/Decimal(1e8):.2f}", f"{r['fcf_net']:.1f}%")
avg_roe=sum(r['roe'] for r in rows.values())/Decimal(5)
avg_gm=sum(r['gross_margin'] for r in rows.values())/Decimal(5)
print('avg roe', avg_roe, 'avg gm', avg_gm)
# 2026Q1 TTM EPS / profit approximate
shares=Decimal('1356921309')
price=Decimal('17.64')
net_ttm=Decimal('1119833030.96')-Decimal('358396418.11')+Decimal('414846479.10')
eps_ttm=net_ttm/shares
bvps=Decimal('11667943414.36')/shares
fcf_2025=rows[2025]['fcf']
fcfps=fcf_2025/shares
div=Decimal('0.143')+Decimal('0.212') # 2025 annual + half-year approximate cash per share
print('ttm net bn', net_ttm/Decimal(1e8), 'eps', eps_ttm, 'bvps', bvps, 'fcfps', fcfps, 'div', div)
print('mcap bn', price*shares/Decimal(1e8), 'pe', price/eps_ttm, 'pb', price/bvps, 'fcfy', fcfps/price*100, 'dy', div/price*100)
