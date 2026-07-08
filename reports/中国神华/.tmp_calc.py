from decimal import Decimal, getcontext
getcontext().prec=28
price=Decimal('41.91')
shares_old=Decimal('198.6852') # 亿股
shares_new=Decimal('216.89434304')
net2025=Decimal('528.49') # 亿元
q1=Decimal('106.67')
annualized=q1*4
bv2025=Decimal('4091.07')
bv_q1=Decimal('4809.02')
ocf2025=Decimal('750.59')
capex=Decimal('217.94') # proxy investment cash out? not capex exact
revenue2025=Decimal('2949.16')
for label,sh in [('old',shares_old),('new',shares_new)]:
    mcap=price*sh
    eps25=net2025/sh
    eps_ann=annualized/sh
    bvps25=bv2025/sh
    bvpsq1=bv_q1/shares_new
    print(label, 'mcap亿', mcap, 'PE25', price/eps25, 'EPS25', eps25, 'PE annQ1', price/eps_ann, 'PB25', price/bvps25, 'BVPS25', bvps25)
print('new PB q1', price/(bv_q1/shares_new), 'bvps q1', bv_q1/shares_new)
print('reported tencent cap', Decimal('9090.04'), 'calc new', price*shares_new)
print('div yield if 2.26', Decimal('2.26')/price)
