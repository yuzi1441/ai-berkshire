import pandas as pd, numpy as np, json, math
from decimal import Decimal, ROUND_HALF_UP
ind=pd.read_csv('data/hengrui/indicator_em.csv')
pro=pd.read_csv('data/hengrui/profit_em.csv')
bal=pd.read_csv('data/hengrui/balance_em.csv')
cas=pd.read_csv('data/hengrui/cash_em.csv')
sina=pd.read_csv('data/hengrui/analysis_sina.csv')
periods=['2021年报','2022年报','2023年报','2024年报','2025年报','2026一季报']
rows=[]
for p in periods:
    i=ind[ind.REPORT_DATE_NAME==p].iloc[0]
    b=bal[bal.REPORT_DATE_NAME==p].iloc[0]
    c=cas[cas.REPORT_DATE_NAME==p].iloc[0]
    pr=pro[pro.REPORT_DATE_NAME==p].iloc[0]
    rows.append({
        'period':p,
        'revenue_bn':i.TOTALOPERATEREVE/1e9,
        'gross_profit_bn':i.MLR/1e9,
        'parent_np_bn':i.PARENTNETPROFIT/1e9,
        'deduct_np_bn':i.KCFJCXSYJLR/1e9,
        'gross_margin_pct':i.XSMLL,
        'roe_wavg_pct':i.ROEJQ,
        'roa_pct':i.ZZCJLL,
        'sales_net_margin_pct':i.XSJLL,
        'cfo_bn':c.NETCASH_OPERATE/1e9,
        'capex_bn':c.CONSTRUCT_LONG_ASSET/1e9,
        'fcf_conservative_bn':(c.NETCASH_OPERATE-c.CONSTRUCT_LONG_ASSET)/1e9,
        'fcf_incl_disposal_bn':(c.NETCASH_OPERATE-c.CONSTRUCT_LONG_ASSET+(0 if pd.isna(c.DISPOSAL_LONG_ASSET) else c.DISPOSAL_LONG_ASSET))/1e9,
        'total_assets_bn':b.TOTAL_ASSETS/1e9,
        'liabilities_bn':b.TOTAL_LIABILITIES/1e9,
        'parent_equity_bn':b.TOTAL_PARENT_EQUITY/1e9,
        'cash_bn':b.MONETARYFUNDS/1e9,
        'current_assets_bn':b.TOTAL_CURRENT_ASSETS/1e9,
        'current_liab_bn':b.TOTAL_CURRENT_LIAB/1e9,
        'share_capital_bn_shares':b.SHARE_CAPITAL/1e9,
        'debt_like_bn':sum((0 if pd.isna(getattr(b,col,np.nan)) else getattr(b,col,np.nan)) for col in ['SHORT_LOAN','NONCURRENT_LIAB_1YEAR','LONG_LOAN','BOND_PAYABLE','LEASE_LIAB'])/1e9,
        'asset_liab_ratio_pct':i.ZCFZL,
        'eps':i.EPSJB,
        'bps':i.BPS,
    })

df=pd.DataFrame(rows)
print(df.round(4).to_markdown(index=False))
# ttm and valuations
rev2025=df.loc[df.period=='2025年报','revenue_bn'].iloc[0]
rev2026q1=df.loc[df.period=='2026一季报','revenue_bn'].iloc[0]
rev2025q1=7.20561112272
np2025=df.loc[df.period=='2025年报','parent_np_bn'].iloc[0]
np2026q1=df.loc[df.period=='2026一季报','parent_np_bn'].iloc[0]
np2025q1=1.87405551998
cfo2025=df.loc[df.period=='2025年报','cfo_bn'].iloc[0]
cfo2026q1=df.loc[df.period=='2026一季报','cfo_bn'].iloc[0]
cfo2025q1=0.55517408851
market=376.79383684698
price=56.77
shares=6.637199874
parent_eq_mrq=df.loc[df.period=='2026一季报','parent_equity_bn'].iloc[0]
cash_mrq=df.loc[df.period=='2026一季报','cash_bn'].iloc[0]
debt_mrq=df.loc[df.period=='2026一季报','debt_like_bn'].iloc[0]
rev_ttm=rev2025+rev2026q1-rev2025q1
np_ttm=np2025+np2026q1-np2025q1
cfo_ttm=cfo2025+cfo2026q1-cfo2025q1
ev=market+debt_mrq-cash_mrq
print('\nVAL')
print(json.dumps({
'price':price,'shares_bn':shares,'marketcap_bn':market,
'ttm_revenue_bn':rev_ttm,'ttm_parent_np_bn':np_ttm,'ttm_cfo_bn':cfo_ttm,
'pe_ttm_calc':market/np_ttm,'ps_ttm_calc':market/rev_ttm,'pb_mrq_calc':market/parent_eq_mrq,
'debt_like_bn':debt_mrq,'cash_bn':cash_mrq,'ev_bn':ev,'ev_sales_ttm':ev/rev_ttm,'ev_np_ttm':ev/np_ttm,'ev_cfo_ttm':ev/cfo_ttm,
},ensure_ascii=False,indent=2))
# cross validate sina annual metrics
s=sina[sina['日期'].astype(str).isin(['2021-12-31','2022-12-31','2023-12-31','2024-12-31','2025-12-31','2026-03-31'])]
print('\nSINA')
print(s[['日期','销售毛利率(%)','净资产收益率(%)','总资产净利润率(%)','每股经营性现金流(元)','资产负债率(%)','总资产(元)']].round(4).to_markdown(index=False))
