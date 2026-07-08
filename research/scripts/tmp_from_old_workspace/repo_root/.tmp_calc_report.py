from decimal import Decimal, getcontext
getcontext().prec=28
# data
price=Decimal('277.00'); shares=Decimal('1541419108'); mc=price*shares
print('A mc CNY', mc, mc/Decimal(1e8))
hk=Decimal('190.50')*Decimal('1426363848')
print('HK mc HKD', hk/Decimal(1e8))
us=Decimal('309.36')*Decimal('110557836')
print('US mc USD bn', us/Decimal(1e9))
# fcf per A share from 2025 FCF 941.7m USD *7.18 / shares 1.4178bn? use A total 1.541bn? perhaps ordinary shares, not A eq. calc per ordinary in CNY
fcf_usd=Decimal('941.7') # m
fx=Decimal('7.18')
print('2025 fcf CNY bn',fcf_usd*fx/1000)
print('fcf yield vs A mc', (fcf_usd*fx/1000)/(mc/Decimal(1e9))*100)
# 2026 Q1 TTM net income: 2025 net 286.933m - 2025Q1 1.270m + 2026Q1 227.357m = 513.020m USD; EPS ADS basic stockanalysis 4.81, ADS; A ordinary EPS in CNY? Tencent says 4.42 CNY likely TTM from A reports. Use it.
# Revenue TTM: stockanalysis 5674m = 2025 5343 - q1 1117 + q1 1513
print('ttm rev', Decimal('5343.033')-Decimal('1117.279')+Decimal('1513.438'))
# q1 yoy rates
for a,b in [('total rev',1513.438,1117.279),('product',1487.329,1108.530),('bruk',1094.843,791.664),('tev',206.241,171.164),('net',227.357,1.270),('op',249.902,11.102)]:
    a=Decimal(str(a)); b=Decimal(str(b)); print(a,b, (a/b-1)*100)
# 2025 product pct
prod={'BRUKINSA':Decimal('3928.489'),'TEVIMBRA':Decimal('737.304'),'XGEVA':Decimal('305.979'),'BLINCYTO':Decimal('104.224'),'KYPROLIS':Decimal('74.974'),'POBEVCY':Decimal('47.400'),'Other':Decimal('83.691')}
tot=Decimal('5282.061')
for k,v in prod.items(): print(k, (v/tot*100).quantize(Decimal('0.1')))
# q1 product pct
prodq={'BRUKINSA':Decimal('1094.843'),'TEVIMBRA':Decimal('206.241'),'XGEVA':Decimal('89.920'),'BLINCYTO':Decimal('34.035'),'KYPROLIS':Decimal('16.971'),'POBEVCY':Decimal('12.127'),'Other':Decimal('33.192')}
totq=Decimal('1487.329')
for k,v in prodq.items(): print('q1',k,(v/totq*100).quantize(Decimal('0.1')))
# gross margin q1 and 2025
print('gm 2025', (Decimal('4674.493')/Decimal('5343.033')*100))
print('product gm 2025', (1-Decimal('668.540')/Decimal('5282.061'))*100)
print('gm q1', (Decimal('1346.223')/Decimal('1513.438')*100))