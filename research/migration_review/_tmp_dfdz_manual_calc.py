from decimal import Decimal, getcontext
getcontext().prec=28
price=Decimal('12.37')
shares=Decimal('1340727007')
reported=Decimal('165.83') # 腾讯行情亿
market_cap_yi=price*shares/Decimal('100000000')
eps=Decimal('0.6802')
bvps=Decimal('4.410641185368')
ocf=Decimal('808247051.74')
capex=Decimal('600000000') # profit distribution says annual investment > 6e8, conservative proxy, not exact capex
fcf=ocf-capex
fcfps=fcf/shares
div=Decimal('0.05')
revps=Decimal('8377482887.40')/shares
print('market_cap_yi',market_cap_yi)
print('pe',price/eps)
print('pb',price/bvps)
print('ocf_yield',ocf/(price*shares)*100)
print('fcf_proxy_yield',fcf/(price*shares)*100, 'fcfps', fcfps)
print('div_yield',div/price*100)
print('revps',revps)
print('q1_adj_np_ex_fv?', Decimal('235825663.52')-Decimal('110419608.96'))
