from decimal import Decimal, getcontext
getcontext().prec=28
price=Decimal('174.20')
shares=Decimal('782573282')
shares_yi=shares/Decimal('100000000')
marketcap_yuan=price*shares
marketcap_yi=marketcap_yuan/Decimal('100000000')
net2025=Decimal('3150142665.04')
q1_2026=Decimal('549952870.75')
q1_2025=Decimal('446499519.83')
ttm_np=net2025+q1_2026-q1_2025
eps2025=Decimal('4.04')
eps_ttm=ttm_np/shares
bvps_q1=Decimal('20.6092')
dps=Decimal('0.70')
fcfps_2025=Decimal('1.260766')
print('shares_yi', shares_yi)
print('marketcap_yi', marketcap_yi)
print('ttm_np_yi', ttm_np/Decimal('100000000'))
print('eps_ttm', eps_ttm)
print('pe_2025', price/eps2025)
print('pe_ttm', price/eps_ttm)
print('pb_q1', price/bvps_q1)
print('div_yield', dps/price*100)
print('fcf_yield_2025', fcfps_2025/price*100)
print('ps_2025', marketcap_yuan/Decimal('21539031405.33'))
