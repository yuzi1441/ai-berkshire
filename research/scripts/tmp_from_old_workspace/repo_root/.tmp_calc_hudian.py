from decimal import Decimal, getcontext
import json, pathlib, textwrap
getcontext().prec=28
p=Decimal('128.83'); shares=Decimal('1924363537')
cap=p*shares
net2025=Decimal('3822306272'); q125=Decimal('762465400'); q126=Decimal('1242081367')
ttm=net2025-q125+q126
ttm_eps=ttm/shares
print('cap', cap)
print('ttm', ttm, 'ttm_eps', ttm_eps, 'ttm_pe', p/ttm_eps)
for eps,g,pe in [('bull',Decimal('2.58'),Decimal('0.25'),Decimal('45')),('base',Decimal('2.58'),Decimal('0.15'),Decimal('35')),('bear',Decimal('2.58'),Decimal('0.02'),Decimal('22'))]:
 target_eps=eps*((1+g)**3)
 target=target_eps*pe
 print(eps, target_eps, target, (target/p-1)*100)
