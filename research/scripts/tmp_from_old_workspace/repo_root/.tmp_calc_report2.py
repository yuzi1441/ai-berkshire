from decimal import Decimal, getcontext
getcontext().prec=28
for name,a,b in [('total rev',1513.438,1117.279),('product',1487.329,1108.530),('bruk',1094.843,791.664),('tev',206.241,171.164),('net',227.357,1.270),('op',249.902,11.102)]:
    a=Decimal(str(a)); b=Decimal(str(b)); print(name, ((a/b-1)*100).quantize(Decimal('0.1')))
prod={'BRUKINSA':Decimal('3928.489'),'TEVIMBRA':Decimal('737.304'),'XGEVA':Decimal('305.979'),'BLINCYTO':Decimal('104.224'),'KYPROLIS':Decimal('74.974'),'POBEVCY':Decimal('47.400'),'Other':Decimal('83.691')}
tot=Decimal('5282.061')
for k,v in prod.items(): print(k, (v/tot*100).quantize(Decimal('0.1')))
prodq={'BRUKINSA':Decimal('1094.843'),'TEVIMBRA':Decimal('206.241'),'XGEVA':Decimal('89.920'),'BLINCYTO':Decimal('34.035'),'KYPROLIS':Decimal('16.971'),'POBEVCY':Decimal('12.127'),'Other':Decimal('33.192')}
totq=Decimal('1487.329')
for k,v in prodq.items(): print('q1',k,(v/totq*100).quantize(Decimal('0.1')))
print('gm 2025 total', (Decimal('4674.493')/Decimal('5343.033')*100).quantize(Decimal('0.1')))
print('product gm 2025', ((1-Decimal('668.540')/Decimal('5282.061'))*100).quantize(Decimal('0.1')))
print('gm q1 total', (Decimal('1346.223')/Decimal('1513.438')*100).quantize(Decimal('0.1')))