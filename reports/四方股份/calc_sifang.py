from decimal import Decimal, ROUND_HALF_UP
vals={
'rev':Decimal('2158066014.06'),'rev_y':Decimal('1828063290.62'),
'cost':Decimal('1479322082.56'),'cost_y':Decimal('1246013467.72'),
'np':Decimal('270665536.47'),'np_y':Decimal('241495156.15'),
'dnp':Decimal('263907214.93'),'dnp_y':Decimal('233553303.79'),
'ocf':Decimal('14115916.45'),'ocf_y':Decimal('186518515.27'),
'rd':Decimal('191736857.99'),'rd_y':Decimal('165129993.74'),
'sales':Decimal('124351486.60'),'sales_y':Decimal('124170769.41'),
'mgmt':Decimal('80395308.78'),'mgmt_y':Decimal('75783515.47'),
'credit':Decimal('-8156649.75'),'credit_y':Decimal('1590988.22'),
'impair':Decimal('-32036545.99'),'impair_y':Decimal('-11788951.71'),
}
def pct(a,b): return (a/b-1)*100
def margin(x, rev): return x/rev*100
for k in ['rev','cost','np','dnp','ocf','rd','sales','mgmt']:
 print(k, float(pct(vals[k], vals[k+'_y'])))
print('gm', margin(vals['rev']-vals['cost'],vals['rev']), margin(vals['rev_y']-vals['cost_y'], vals['rev_y']))
print('np margin', margin(vals['np'], vals['rev']), margin(vals['np_y'], vals['rev_y']))
print('rd ratio', margin(vals['rd'], vals['rev']), margin(vals['rd_y'], vals['rev_y']))
print('sales ratio', margin(vals['sales'], vals['rev']), margin(vals['sales_y'], vals['rev_y']))
print('mgmt ratio', margin(vals['mgmt'], vals['rev']), margin(vals['mgmt_y'], vals['rev_y']))
print('impair+credit vs rev', margin(vals['credit']+vals['impair'], vals['rev']), margin(vals['credit_y']+vals['impair_y'], vals['rev_y']))
