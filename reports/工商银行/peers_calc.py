from decimal import Decimal, getcontext
getcontext().prec=28
hkd=Decimal('0.8654')
peers=[
 ('????A','601398.SH',Decimal('7.12'),Decimal('1.01'),Decimal('11.06'),'CNY'),
 ('????A','601288.SH',Decimal('5.97'),Decimal('0.78'),Decimal('8.02'),'CNY'),
 ('????A','601939.SH',Decimal('9.67'),Decimal('1.32'),Decimal('13.33'),'CNY'),
 ('????A','601988.SH',Decimal('5.64'),Decimal('0.59'),Decimal('7.90'),'CNY'),
 ('????A','600036.SH',Decimal('37.73'),Decimal('5.55'),Decimal('39.77'),'CNY'),
 ('????H','01398.HK',Decimal('6.43')*hkd,Decimal('1.01'),Decimal('11.06'),'CNY-equiv'),
 ('????H','01288.HK',Decimal('5.30')*hkd,Decimal('0.78'),Decimal('8.02'),'CNY-equiv'),
 ('????H','00939.HK',Decimal('7.85')*hkd,Decimal('1.32'),Decimal('13.33'),'CNY-equiv'),
 ('????H','03988.HK',Decimal('4.82')*hkd,Decimal('0.59'),Decimal('7.90'),'CNY-equiv'),
 ('????H','03968.HK',Decimal('45.36')*hkd,Decimal('5.55'),Decimal('39.77'),'CNY-equiv'),
]
for name,t,p,e,b,c in peers:
 print(name,t,'price_cny',round(p,4),'PE',round(p/e,2),'PB',round(p/b,2))
