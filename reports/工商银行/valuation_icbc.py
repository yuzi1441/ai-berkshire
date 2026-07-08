from decimal import Decimal, getcontext
getcontext().prec=28
A=Decimal('7.12')
H=Decimal('6.43')
hkd_cny=Decimal('0.8654')
H_cny=H*hkd_cny
eps25=Decimal('1.00')
eps_ttm=Decimal('1.01')
bvps25=Decimal('10.83')
bvps_q1=Decimal('11.06')
dps=Decimal('0.310')
shares_total=Decimal('356.407') # bn
A_shares=Decimal('269.612')
H_shares=Decimal('86.794')
market_cap_A_basis=A*shares_total
market_cap_mixed=A*A_shares + H_cny*H_shares
print('H_cny', H_cny)
for label, price, bv in [('A',A,bvps_q1),('H_CNY',H_cny,bvps_q1)]:
 print(label, 'PE25', price/eps25, 'PE_TTM', price/eps_ttm, 'PB_Q1', price/bv, 'PB_2025', price/bvps25, 'yield_on_RMB_DPS', dps/price)
print('market_cap_A_basis_bn_CNY', market_cap_A_basis)
print('market_cap_mixed_bn_CNY', market_cap_mixed)
print('A_market_cap_reported_lixinger_bn', Decimal('25400'))
# justified PB = (ROE-g)/(coe-g)
scenarios=[
 ('bear_no_haircut',Decimal('0.075'),Decimal('0.105'),Decimal('0.005'),Decimal('1.00')),
 ('stress_10pct_book_haircut',Decimal('0.070'),Decimal('0.105'),Decimal('0.005'),Decimal('0.90')),
 ('base_conservative',Decimal('0.085'),Decimal('0.095'),Decimal('0.010'),Decimal('1.00')),
 ('quality_case',Decimal('0.095'),Decimal('0.090'),Decimal('0.015'),Decimal('1.00')),
]
for name,roe,coe,g,haircut in scenarios:
 pb=(roe-g)/(coe-g)
 value=bvps_q1*haircut*pb
 print(name, 'pb', pb, 'value_CNY', value, 'mos_A', (value-A)/A, 'mos_H_CNY', (value-H_cny)/H_cny)
PY
