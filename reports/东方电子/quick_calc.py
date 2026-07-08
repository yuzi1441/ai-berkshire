from decimal import Decimal, getcontext
getcontext().prec=28
price=Decimal('12.37')
shares=Decimal('1340727007')
cap=price*shares
net_profit=Decimal('911992429.9')
deduct=Decimal('730100077.37')
revenue=Decimal('8377482887.4')
equity=Decimal('5913466000') # approximate from csv exact maybe use script later
bps=Decimal('4.410641185368')
eps=Decimal('0.6802')
div=Decimal('0.05')
print('cap',cap, 'yi',cap/Decimal('1e8'))
print('pe',cap/net_profit,'deduct_pe',cap/deduct,'ps',cap/revenue,'pb',price/bps,'yield',div/price*100)
