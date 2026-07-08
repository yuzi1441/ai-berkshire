from decimal import Decimal, getcontext
getcontext().prec=28
# all RMB in billions unless per share; financials from annual report 百万元 converted to 亿元 by /100
shares=Decimal('19.869') # billion shares pre placement; post around 21.689? use quote provider says 21.689bn total incl placing for market cap? annual year-end 19.869. For EPS reported uses 19.869.
price_A=Decimal('41.91')
price_H=Decimal('41.02')
hkd_cny=Decimal('0.916')
price_H_cny=price_H*hkd_cny
# quote market caps from Tencent (亿 local currency)
mc_A=Decimal('9090.04') # 亿 CNY total market cap in qq quote
mc_H_hkd=Decimal('8897.0060') # 亿 HKD total cap by total shares? quote
mc_H_cny=mc_H_hkd*hkd_cny
# annual 2025
rev=Decimal('2949.16')
op=Decimal('755.32')
pbt=Decimal('793.39')
net_parent=Decimal('528.49')
net=Decimal('627.83')
eps=Decimal('2.660')
bvps=Decimal('20.59')
ocf=Decimal('750.59')
capex=Decimal('483.98')
fcf=ocf-capex
fcfps=fcf/shares
# dividends: 0.98 interim+1.03 final=2.01; total cash dividend 418.11亿
DPS=Decimal('2.01')
div_total=Decimal('418.11')
# cash/debt
cash=Decimal('967.72')
restricted=Decimal('176.37')
cash_eq=Decimal('232.88')
short=Decimal('4.09')
one_year=Decimal('93.64')
long=Decimal('282.68')
bond=Decimal('0')
lease=Decimal('12.77') # from funding debt table lease incl one-year if used
interest_debt=short+one_year+long+bond # exclude lease base
interest_debt2=interest_debt+lease
net_cash=cash-interest_debt
# margins
cost=Decimal('1914.65')
gross=(rev-cost)/rev*100
net_margin=net/rev*100
parent_margin=net_parent/rev*100
op_margin=op/rev*100
roa=net/Decimal('6277.61')*100 # period-end asset basis; annual reports says total asset return 10.0
# q1 2026
q1_rev=Decimal('703.97'); q1_pbt=Decimal('165.94'); q1_np=Decimal('106.67'); q1_ocf=Decimal('173.63'); q1_capex=Decimal('95.83')
q1_eps=Decimal('0.530')
ttm_eps=eps - Decimal('0.601') + q1_eps
# valuations
def ratio(a,b): return a/b
print('A mc from price old shares 亿=', price_A*shares*Decimal('10'))
print('A mc quote 亿=',mc_A)
print('H price CNY=',price_H_cny,'H mc CNY 亿=',mc_H_cny)
for name,p,mc in [('A',price_A,mc_A),('H_CNY',price_H_cny,mc_H_cny)]:
 print('\n',name)
 print('PE 2025',p/eps,'TTM',p/ttm_eps,'PB',p/bvps,'divyield',DPS/p*100)
 print('FCF yield mcap',fcf/mc*100,'P/FCF',mc/fcf)
 print('Earnings yield',eps/p*100)
print('\nMargins gross net parent op ROA',gross,net_margin,parent_margin,op_margin,roa)
print('FCF',fcf,'fcfps',fcfps,'capex/ocf',capex/ocf*100,'div/ocf',div_total/ocf*100,'div/fcf',div_total/fcf*100,'div/netparent',div_total/net_parent*100)
print('cash debt netcash debt_with_lease netcash2',cash,interest_debt,net_cash,interest_debt2,cash-interest_debt2,'liab/assets',Decimal('1463.10')/Decimal('6277.61')*100)
# segment tables values 百万元 -> 亿元
segments=[('煤炭',2212.32,1546.31,465.97),('发电',891.39,730.52,126.27),('铁路',437.10,271.58,129.01),('港口',70.20,37.44,26.31),('航运',39.89,35.32,2.69),('煤化工',57.22,53.08,0.58),('其他',7.94,0,42.75)]
seg_pbt_sum=sum(Decimal(str(x[3])) for x in segments)
for s,rev_s,cost_s,pbt_s in segments:
 revd=Decimal(str(rev_s)); costd=Decimal(str(cost_s)); pbtd=Decimal(str(pbt_s))
 print(s,'gross%', (revd-costd)/revd*100 if revd else None, 'pbt share',pbtd/Decimal('793.39')*100)
# scenario intrinsic: normalized EPS, terminal PE, dividends 2.0-2.1
for scen,neps,pe in [('熊',Decimal('2.0'),Decimal('10')),('基准',Decimal('2.5'),Decimal('12')),('牛',Decimal('3.0'),Decimal('14'))]:
 value=neps*pe
 print('scenario',scen,'eps',neps,'pe',pe,'exdiv value',value,'with one-year div',value+DPS)
PY
