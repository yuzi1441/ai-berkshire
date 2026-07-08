from decimal import Decimal, getcontext
getcontext().prec=28
A=Decimal('7.12'); H=Decimal('6.43'); fx=Decimal('0.8654')
Hc=H*fx
eps=Decimal('1.01'); bv=Decimal('11.06'); dps=Decimal('0.310')
shares=Decimal('356406257089'); Ash=Decimal('269612212539'); Hsh=Decimal('86794044550')
print('Hc', Hc)
print('A PE',A/eps,'PB',A/bv,'yield',dps/A)
print('H PE',Hc/eps,'PB',Hc/bv,'yield',dps/Hc)
print('A all cap CNY',A*shares)
print('mixed cap CNY',A*Ash + Hc*Hsh)
for name,roe,coe,g,haircut in [
('bear_no_haircut',Decimal('0.075'),Decimal('0.105'),Decimal('0.005'),Decimal('1.00')),
('stress_10pct_book_haircut',Decimal('0.070'),Decimal('0.105'),Decimal('0.005'),Decimal('0.90')),
('base_conservative',Decimal('0.085'),Decimal('0.095'),Decimal('0.010'),Decimal('1.00'))]:
 pb=(roe-g)/(coe-g); value=bv*haircut*pb
 print(name,pb,value,(value-A)/A,(value-Hc)/Hc)
