from decimal import Decimal
shares=Decimal('824157988')
price=Decimal('106.75')
np2025=Decimal('1869300805.65')
np25q1=Decimal('370082216.76')
np26q1=Decimal('398869282.78')
ttm=np2025-np25q1+np26q1
eps_ttm=ttm/shares
rev2025=Decimal('13800251663.95')
rev25q1=Decimal('2477948927.49')
rev26q1=Decimal('2907566494.56')
revttm=rev2025-rev25q1+rev26q1
print('np_ttm亿', ttm/Decimal('1e8'), 'eps_ttm', eps_ttm, 'pe', price/eps_ttm)
print('rev_ttm亿', revttm/Decimal('1e8'), 'ps ttm', (price*shares)/revttm)
print('mcap亿', price*shares/Decimal('1e8'))
print('bvps q1', Decimal('21961890462.79')/shares, 'pb q1', price/(Decimal('21961890462.79')/shares))
print('net cash+trading q1亿', (Decimal('7045475945.16')+Decimal('1874561458.46')-Decimal('1319501252.51'))/Decimal('1e8'))
