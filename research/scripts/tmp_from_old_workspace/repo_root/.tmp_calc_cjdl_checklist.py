from decimal import Decimal
roe=[Decimal('14.92'),Decimal('9.32'),Decimal('13.52'),Decimal('15.71'),Decimal('15.90')]
print('5y roe avg', sum(roe)/len(roe))
print('3y roe avg', sum(roe[-3:])/3)
rev=Decimal('86241940222.20'); cost=Decimal('25881578129.36')+Decimal('7067072381.81')
print('gross margin main', (rev-cost)/rev*100)
ocf=Decimal('60562925570.41'); capex=Decimal('18488466859.29'); shares=Decimal('24468217716')
fcf=ocf-capex
print('fcf',fcf, 'per share', fcf/shares)
price=Decimal('27.19')
print('market cap bn', price*shares/Decimal(1e8))
print('ttm eps', Decimal('1.4101')-Decimal('0.2117')+Decimal('0.2763'))
print('bvps q1', Decimal('227903660002.59')/shares)
print('net debt q1 rough', (Decimal('16104360211.77')+Decimal('77502232264.73')+Decimal('162047202279.91')+Decimal('33479068249.78')+Decimal('503464125.20')-Decimal('4916388708.19'))/Decimal(1e8))
print('net debt/net profit', (Decimal('16104360211.77')+Decimal('77502232264.73')+Decimal('162047202279.91')+Decimal('33479068249.78')+Decimal('503464125.20')-Decimal('4916388708.19'))/Decimal('34502809176.39'))
