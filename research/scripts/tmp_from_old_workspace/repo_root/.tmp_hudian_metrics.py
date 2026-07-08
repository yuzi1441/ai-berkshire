import pandas as pd, json, pathlib, math
prof=pd.read_csv('data/hudian_profit_em.csv', parse_dates=['REPORT_DATE'])
bal=pd.read_csv('data/hudian_balance_em.csv', parse_dates=['REPORT_DATE'])
cf=pd.read_csv('data/hudian_cashflow_em.csv', parse_dates=['REPORT_DATE'])
# annual dates for 2021-2025 and q1 2026
rows=[]
for y in [2021,2022,2023,2024,2025]:
 d=pd.Timestamp(f'{y}-12-31')
 p=prof[prof['REPORT_DATE'].dt.date==d.date()].iloc[0]
 b=bal[bal['REPORT_DATE'].dt.date==d.date()].iloc[0]
 c=cf[cf['REPORT_DATE'].dt.date==d.date()].iloc[0]
 rows.append({
  'year':y,
  'revenue_bn':p['TOTAL_OPERATE_INCOME']/1e8,
  'parent_np_bn':p['PARENT_NETPROFIT']/1e8,
  'deduct_np_bn':p['DEDUCT_PARENT_NETPROFIT']/1e8,
  'gross_margin_pct':(p['TOTAL_OPERATE_INCOME']-p['OPERATE_COST'])/p['TOTAL_OPERATE_INCOME']*100,
  'op_margin_pct':p['OPERATE_PROFIT']/p['TOTAL_OPERATE_INCOME']*100,
  'net_margin_pct':p['PARENT_NETPROFIT']/p['TOTAL_OPERATE_INCOME']*100,
  'rd_bn':p['RESEARCH_EXPENSE']/1e8 if not pd.isna(p['RESEARCH_EXPENSE']) else None,
  'ocf_bn':c['NETCASH_OPERATE']/1e8,
  'capex_bn':c['CONSTRUCT_LONG_ASSET']/1e8 if not pd.isna(c['CONSTRUCT_LONG_ASSET']) else None,
  'fcf_simple_bn':(c['NETCASH_OPERATE']-c['CONSTRUCT_LONG_ASSET'])/1e8 if not pd.isna(c['CONSTRUCT_LONG_ASSET']) else None,
  'cash_bn':b['MONETARYFUNDS']/1e8,
  'assets_bn':b['TOTAL_ASSETS']/1e8,
  'liabilities_bn':b['TOTAL_LIABILITIES']/1e8,
  'equity_parent_bn':b.get('PARENT_EQUITY', float('nan'))/1e8 if 'PARENT_EQUITY' in b.index else None,
  'shares_bn':b['SHARE_CAPITAL']/1e8,
 })
q1=prof[prof['REPORT_DATE'].dt.date==pd.Timestamp('2026-03-31').date()].iloc[0]
q1b=bal[bal['REPORT_DATE'].dt.date==pd.Timestamp('2026-03-31').date()].iloc[0]
q1c=cf[cf['REPORT_DATE'].dt.date==pd.Timestamp('2026-03-31').date()].iloc[0]
q1dict={'revenue_bn':q1['TOTAL_OPERATE_INCOME']/1e8,'parent_np_bn':q1['PARENT_NETPROFIT']/1e8,'deduct_np_bn':q1['DEDUCT_PARENT_NETPROFIT']/1e8,'gross_margin_pct':(q1['TOTAL_OPERATE_INCOME']-q1['OPERATE_COST'])/q1['TOTAL_OPERATE_INCOME']*100,'op_margin_pct':q1['OPERATE_PROFIT']/q1['TOTAL_OPERATE_INCOME']*100,'ocf_bn':q1c['NETCASH_OPERATE']/1e8,'cash_bn':q1b['MONETARYFUNDS']/1e8,'assets_bn':q1b['TOTAL_ASSETS']/1e8,'liabilities_bn':q1b['TOTAL_LIABILITIES']/1e8,'shares_bn':q1b['SHARE_CAPITAL']/1e8}
# quote parse manual from tencent/sina fetched
price=128.83
shares_total=1924363537
market_cap=price*shares_total
np2025=3822306272
dednp2025=3760567906
revenue2025=18945220585
np_q1_2026=1242081367
revenue_q1_2026=6214156406
metrics={
 'price':price,'shares_total':shares_total,'market_cap_yuan':market_cap,'market_cap_bn':market_cap/1e8,
 'pe_2025':market_cap/np2025,'pe_deduct_2025':market_cap/dednp2025,'ps_2025':market_cap/revenue2025,
 'pe_q1annualized':market_cap/(np_q1_2026*4),'ps_q1annualized':market_cap/(revenue_q1_2026*4),
 'dividend_2025_cash':962181768.5,'dividend_yield':962181768.5/market_cap,
 'q1_2026_yoy_rev': (revenue_q1_2026-4037627327)/4037627327,
 'q1_2026_yoy_np': (np_q1_2026-762465400)/762465400,
}
summary={'annual':rows,'q1_2026':q1dict,'valuation':metrics}
pathlib.Path('data/hudian_metrics_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
