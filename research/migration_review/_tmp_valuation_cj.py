from decimal import Decimal, getcontext
getcontext().prec=28
shares=Decimal('24468217716'); price=Decimal('27.19')
scenarios={
 '保守': {'eps0':Decimal('1.35'),'g':Decimal('0.01'),'r':Decimal('0.09'),'payout':Decimal('0.70'),'terminal_g':Decimal('0.00'),'years':10},
 '基准': {'eps0':Decimal('1.48'),'g':Decimal('0.03'),'r':Decimal('0.08'),'payout':Decimal('0.70'),'terminal_g':Decimal('0.01'),'years':10},
 '乐观': {'eps0':Decimal('1.60'),'g':Decimal('0.045'),'r':Decimal('0.075'),'payout':Decimal('0.72'),'terminal_g':Decimal('0.015'),'years':10},
}
print('DDM intrinsic per share: dividends years1-10 + terminal dividend/(r-g) discounted')
for name,s in scenarios.items():
 eps=s['eps0']; g=s['g']; r=s['r']; payout=s['payout']; tg=s['terminal_g']; n=s['years']
 pv=Decimal(0)
 for t in range(1,n+1):
  epst=eps*((1+g)**t); div=epst*payout; pv += div/((1+r)**t)
 epsn=eps*((1+g)**n); div_next=epsn*(1+tg)*payout
 tv=div_next/(r-tg)
 pv_tv=tv/((1+r)**n)
 intrinsic=pv+pv_tv
 print(name,'value',round(intrinsic,2),'upside%',round((intrinsic/price-1)*100,1),'terminal_value',round(tv,2),'pv_div',round(pv,2),'pv_tv',round(pv_tv,2))
for name,eps,fair_pe in [('保守',Decimal('1.35'),Decimal('15')),('基准',Decimal('1.48'),Decimal('18')),('乐观',Decimal('1.60'),Decimal('20'))]:
 val=eps*fair_pe
 print('PE',name,round(val,2),round((val/price-1)*100,1))
for eps,g,payout in [(Decimal('1.48'),Decimal('0.02'),Decimal('0.70')),(Decimal('1.60'),Decimal('0.03'),Decimal('0.70'))]:
 div1=eps*(1+g)*payout
 print('implied return gordon', round(div1/price*100+g*100,2), 'div1', round(div1,2))
