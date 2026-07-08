from decimal import Decimal, getcontext
getcontext().prec=28
D=Decimal
vals={
'rev_q1_2026':D('2158066014.06'),'rev_q1_2025':D('1828063290.62'),
'cogs_q1_2026':D('1479322082.56'),'cogs_q1_2025':D('1246013467.72'),
'sales_q1_2026':D('124351486.60'),'sales_q1_2025':D('124170769.41'),
'admin_q1_2026':D('80395308.78'),'admin_q1_2025':D('75783515.47'),
'rd_q1_2026':D('191736857.99'),'rd_q1_2025':D('165129993.74'),
'fin_q1_2026':D('-10805800.63'),'fin_q1_2025':D('-15179408.39'),
'np_q1_2026':D('270665536.47'),'np_q1_2025':D('241495156.15'),
'ded_np_q1_2026':D('263907214.93'),'ded_np_q1_2025':D('233553303.79'),
'ocf_q1_2026':D('14115916.45'),'ocf_q1_2025':D('186518515.27'),
'ar_20260331':D('1400178134.12'),'ar_20251231':D('1449451300.85'),
'inv_20260331':D('2362926621.18'),'inv_20251231':D('2325246777.10'),
'contract_asset_20260331':D('2512769384.37'),'contract_asset_20251231':D('2200822704.22'),
'contract_liab_20260331':D('1728923281.90'),'contract_liab_20251231':D('1992955064.77'),
'cash_20260331':D('2712726894.49'),'cash_20251231':D('3781954632.22'),
'trading_20260331':D('1503008035.02'),'trading_20251231':D('500000000.00'),
'assets_20260331':D('12872747440.96'),'assets_20251231':D('12705127033.69'),
'liab_20260331':D('7700922742.64'),'liab_20251231':D('7808950596.31'),
'equity_attr_20260331':D('5170362121.99'),'equity_attr_20251231':D('4894860789.37'),
'rev_2025':D('8193310113.95'),'rev_2024':D('6950934596.87'),
'cogs_2025':D('5716993593.17'),'cogs_2024':D('4703368425.19'),
'np_2025':D('828970422.18'),'ded_np_2025':D('800184956.03'),'ocf_2025':D('1224656463.11'),
'capex_2025':D('211480579.53'), #购建固定资产、无形资产和其他长期资产支付的现金 needs verify line 318x
'dividend_2025_plan':D('599892120'),
'price':D('60.96'),'shares_quote':D('833105500')
}
def pct(a): return (a*100).quantize(D('0.01'))
def yoy(cur,prev): return pct((cur-prev)/prev)
def ratio(a,b): return pct(a/b)
def yuan_to_yi(x): return (x/D('100000000')).quantize(D('0.01'))
metrics={}
metrics['q1_gross_margin_2026']=ratio(vals['rev_q1_2026']-vals['cogs_q1_2026'], vals['rev_q1_2026'])
metrics['q1_gross_margin_2025']=ratio(vals['rev_q1_2025']-vals['cogs_q1_2025'], vals['rev_q1_2025'])
for key in ['sales','admin','rd','fin']:
    metrics[f'{key}_rate_q1_2026']=ratio(vals[f'{key}_q1_2026'], vals['rev_q1_2026'])
    metrics[f'{key}_rate_q1_2025']=ratio(vals[f'{key}_q1_2025'], vals['rev_q1_2025'])
metrics['net_margin_q1_2026']=ratio(vals['np_q1_2026'], vals['rev_q1_2026'])
metrics['net_margin_q1_2025']=ratio(vals['np_q1_2025'], vals['rev_q1_2025'])
metrics['ocf_np_q1_2026']=ratio(vals['ocf_q1_2026'], vals['np_q1_2026'])
metrics['ocf_np_q1_2025']=ratio(vals['ocf_q1_2025'], vals['np_q1_2025'])
metrics['rev_yoy_q1']=yoy(vals['rev_q1_2026'], vals['rev_q1_2025'])
metrics['np_yoy_q1']=yoy(vals['np_q1_2026'], vals['np_q1_2025'])
metrics['ded_np_yoy_q1']=yoy(vals['ded_np_q1_2026'], vals['ded_np_q1_2025'])
metrics['ocf_yoy_q1']=yoy(vals['ocf_q1_2026'], vals['ocf_q1_2025'])
metrics['ar_change_q1']=yoy(vals['ar_20260331'], vals['ar_20251231'])
metrics['inv_change_q1']=yoy(vals['inv_20260331'], vals['inv_20251231'])
metrics['contract_asset_change_q1']=yoy(vals['contract_asset_20260331'], vals['contract_asset_20251231'])
metrics['contract_liab_change_q1']=yoy(vals['contract_liab_20260331'], vals['contract_liab_20251231'])
metrics['cash_plus_trading_20260331_yi']=yuan_to_yi(vals['cash_20260331']+vals['trading_20260331'])
metrics['cash_plus_trading_20251231_yi']=yuan_to_yi(vals['cash_20251231']+vals['trading_20251231'])
metrics['debt_asset_20260331']=ratio(vals['liab_20260331'], vals['assets_20260331'])
metrics['debt_asset_20251231']=ratio(vals['liab_20251231'], vals['assets_20251231'])
metrics['annual_gross_margin_2025']=ratio(vals['rev_2025']-vals['cogs_2025'], vals['rev_2025'])
metrics['annual_gross_margin_2024']=ratio(vals['rev_2024']-vals['cogs_2024'], vals['rev_2024'])
metrics['annual_ocf_np_2025']=ratio(vals['ocf_2025'], vals['np_2025'])
metrics['market_cap_yi']=yuan_to_yi(vals['price']*vals['shares_quote'])
np_ttm=vals['np_2025']+vals['np_q1_2026']-vals['np_q1_2025']
metrics['np_ttm_yi']=yuan_to_yi(np_ttm)
metrics['pe_ttm']=(vals['price']*vals['shares_quote']/np_ttm).quantize(D('0.01'))
metrics['pb_q1']=(vals['price']*vals['shares_quote']/vals['equity_attr_20260331']).quantize(D('0.01'))
metrics['div_yield_plan_2025']=ratio(vals['dividend_2025_plan'], vals['price']*vals['shares_quote'])
metrics['ar_plus_contract_asset_20260331_yi']=yuan_to_yi(vals['ar_20260331']+vals['contract_asset_20260331'])
metrics['ar_plus_contract_asset_to_rev_2025']=ratio(vals['ar_20260331']+vals['contract_asset_20260331'], vals['rev_2025'])
metrics['inventory_to_rev_2025']=ratio(vals['inv_20260331'], vals['rev_2025'])
for k,v in metrics.items(): print(k, v)
