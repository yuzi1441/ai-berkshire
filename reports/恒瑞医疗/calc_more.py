from decimal import Decimal, getcontext
getcontext().prec=28
price=Decimal('56.77')
scenarios=[('乐观',Decimal('102.8')),('中性',Decimal('63.5')),('悲观',Decimal('39.7'))]
for name,target in scenarios:
    cagr=(target/price) ** (Decimal(1)/Decimal(3)) - 1
    print(name, target, float(cagr*100))
# CAGR revenue 2021-2025, profit
rev21=Decimal('25905526375.8'); rev25=Decimal('31629416193.83')
np21=Decimal('4530217550.47'); np25=Decimal('7711054811.98')
for label,a,b in [('rev',rev21,rev25),('np',np21,np25)]:
    c=(b/a) ** (Decimal(1)/Decimal(4)) - 1
    print(label,float(c*100))
# ROE avg 2021-2025 from values
roes=[Decimal('13.96'),Decimal('10.89'),Decimal('10.99'),Decimal('14.73'),Decimal('14.26')]
print(sum(roes)/len(roes))
# license share 33.9240996056 /316.2941619383? innovation share
print(Decimal('33.9240996056')/Decimal('316.2941619383')*100)
print(Decimal('163.42')/Decimal('316.2941619383')*100)
print(Decimal('163.42')/Decimal('280.1344834768')*100)
# current q1 innovation share: 45.26 total sales? drug sales=45.26/.6169
print(Decimal('45.26')/Decimal('0.6169'))