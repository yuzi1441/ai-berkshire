from decimal import Decimal, getcontext
getcontext().prec=28
price=Decimal('21.11')
shares=Decimal('1018622249')
annual={
'2025_revenue':Decimal('14991906066.24'),
'2025_np':Decimal('1167210009.73'),
'2025_deduct_np':Decimal('1121788879.27'),
'2025_ocf':Decimal('2670382574.97'),
'2025_capex':Decimal('248448282.49'),
'2025_equity':Decimal('12150593337.07'),
'2025_assets':Decimal('26251404488.84'),
'2025_liab':Decimal('12871238124.27'),
'cash':Decimal('7527186625.20'),
'debt':Decimal('275300000.00')+Decimal('120686664.56')+Decimal('35027641.42'),
'dividend_total':Decimal('467547612.29'),
'div_ps':Decimal('0.459'),
}
q1={'rev':Decimal('2377751582.79'),'np':Decimal('111046230.14'),'equity':Decimal('12272843036.91'),'assets':Decimal('25796351253.46'),'liab':Decimal('12277198385.27')}
fcf=annual['2025_ocf']-annual['2025_capex']
metrics={
 'market_cap_yi': price*shares/Decimal(1e8),
 'revenue_yi': annual['2025_revenue']/Decimal(1e8),
 'np_yi': annual['2025_np']/Decimal(1e8),
 'deduct_np_yi': annual['2025_deduct_np']/Decimal(1e8),
 'ocf_yi': annual['2025_ocf']/Decimal(1e8),
 'fcf_yi': fcf/Decimal(1e8),
 'fcfps': fcf/shares,
 'pe': price/(annual['2025_np']/shares),
 'pb': price/(annual['2025_equity']/shares),
 'fcf_yield': fcf/(price*shares)*100,
 'div_yield': annual['div_ps']/price*100,
 'debt_yi': annual['debt']/Decimal(1e8),
 'net_cash_yi': (annual['cash']-annual['debt'])/Decimal(1e8),
 'q1_rev_yi': q1['rev']/Decimal(1e8),
 'q1_np_yi': q1['np']/Decimal(1e8),
 'q1_roa': q1['np']/q1['assets']*100,
 'liab_ratio': annual['2025_liab']/annual['2025_assets']*100,
 'q1_liab_ratio': q1['liab']/q1['assets']*100,
}
for k,v in metrics.items(): print(k, round(v,4))