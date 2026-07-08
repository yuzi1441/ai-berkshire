import pandas as pd, math, json
ind=pd.read_csv('data_snapshots/em_indicator.csv')
profit=pd.read_csv('data_snapshots/em_profit.csv')
bal=pd.read_csv('data_snapshots/em_balance.csv')
cash=pd.read_csv('data_snapshots/em_cash.csv')
annual_ind=ind[ind['REPORT_TYPE'].eq('年报')].copy(); annual_ind['year']=annual_ind['REPORT_DATE'].str[:4].astype(int)
rows=[]
for _,r in annual_ind[annual_ind['year'].between(2021,2025)].sort_values('year').iterrows():
    date=r['REPORT_DATE']; year=r['year']
    prow=profit[(profit['REPORT_DATE'].eq(date)) & (profit['REPORT_TYPE'].eq('年报'))].iloc[0]
    brow=bal[(bal['REPORT_DATE'].eq(date)) & (bal['REPORT_TYPE'].eq('年报'))].iloc[0]
    crow=cash[(cash['REPORT_DATE'].eq(date)) & (cash['REPORT_TYPE'].eq('年报'))].iloc[0]
    ocf=float(crow['NETCASH_OPERATE']); capex=float(crow['CONSTRUCT_LONG_ASSET']); fcf=ocf-capex
    debt=sum(float(x) for x in [brow.get('SHORT_LOAN'),brow.get('LONG_LOAN'),brow.get('NONCURRENT_LIAB_1YEAR'),brow.get('LEASE_LIAB')] if pd.notna(x))
    rows.append({
      '年份':year,'营收(亿)':r['TOTALOPERATEREVE']/1e8,'归母净利(亿)':r['PARENTNETPROFIT']/1e8,'扣非净利(亿)':r['KCFJCXSYJLR']/1e8,'经营现金流(亿)':ocf/1e8,'资本开支(亿)':capex/1e8,'FCF(亿)':fcf/1e8,
      'ROE%':r['ROEJQ'],'ROA%':r['ZZCJLL'],'毛利率%':r['XSMLL'],'净利率%':r['XSJLL'],'经营利润率%':float(prow['OPERATE_PROFIT'])/float(r['TOTALOPERATEREVE'])*100,'资产负债率%':r['ZCFZL'],'现金(亿)':brow['MONETARYFUNDS']/1e8,'有息债务(亿)':debt/1e8,'EPS':r['EPSJB'],'BPS':r['BPS'],'股本估算(亿股)':r['PARENTNETPROFIT']/r['EPSJB']/1e8,'PS收入每股':r['TOTALOPERATEREVE']/(r['PARENTNETPROFIT']/r['EPSJB'])
    })
df=pd.DataFrame(rows)
for col in df.columns:
    if col!='年份': df[col]=df[col].astype(float).round(2)
print(df.to_markdown(index=False))
# 2026Q1
q=ind[ind['REPORT_DATE_NAME'].eq('2026一季报')].iloc[0]
qb=bal[bal['REPORT_DATE_NAME'].eq('2026一季报')].iloc[0]
qc=cash[cash['REPORT_DATE_NAME'].eq('2026一季报')].iloc[0]
print('\nQ1', {k:round(v,2) for k,v in {'营收亿':q['TOTALOPERATEREVE']/1e8,'归母净利亿':q['PARENTNETPROFIT']/1e8,'扣非净利亿':q['KCFJCXSYJLR']/1e8,'经营现金流亿':qc['NETCASH_OPERATE']/1e8,'现金亿':qb['MONETARYFUNDS']/1e8,'有息债务亿':(qb['SHORT_LOAN']+qb['NONCURRENT_LIAB_1YEAR']+qb['LEASE_LIAB'])/1e8,'资产负债率':q['ZCFZL']}.items()})
