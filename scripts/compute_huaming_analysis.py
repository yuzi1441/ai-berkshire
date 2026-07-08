import pandas as pd, json, math, os
from decimal import Decimal
# Build table from EM and official summary known values
ind=pd.read_csv('data/002270/indicator_em_20260706.csv')
cash=pd.read_csv('data/002270/cash_em_20260706.csv')
years=['2021年报','2022年报','2023年报','2024年报','2025年报']
rows=[]
for y in years:
    r=ind[ind.REPORT_DATE_NAME.eq(y)].iloc[0]
    c=cash[cash.REPORT_DATE_NAME.eq(y)].iloc[0]
    fcf=c.NETCASH_OPERATE - c.CONSTRUCT_LONG_ASSET
    rows.append({
        'year':y[:4],
        'revenue_yi':r.TOTALOPERATEREVE/1e8,
        'parent_np_yi':r.PARENTNETPROFIT/1e8,
        'deduct_np_yi':r.KCFJCXSYJLR/1e8,
        'ocf_yi':c.NETCASH_OPERATE/1e8,
        'capex_yi':c.CONSTRUCT_LONG_ASSET/1e8,
        'fcf_yi':fcf/1e8,
        'gross_margin_pct':r.XSMLL,
        'net_margin_pct':r.XSJLL,
        'roe_pct':r.ROEJQ,
        'debt_asset_pct':r.ZCFZL,
        'eps':r.EPSJB,
        'bps':r.BPS,
        'fcf_per_share': fcf/896225431,
    })
df=pd.DataFrame(rows)
# YoY/CAGR
for col in ['revenue_yi','parent_np_yi','deduct_np_yi','ocf_yi','fcf_yi']:
    df[col+'_yoy_pct']=df[col].pct_change()*100
cagr_rev=(df.iloc[-1].revenue_yi/df.iloc[0].revenue_yi)**(1/4)-1
cagr_np=(df.iloc[-1].parent_np_yi/df.iloc[0].parent_np_yi)**(1/4)-1
# Q1
q=ind[ind.REPORT_DATE_NAME.eq('2026一季报')].iloc[0]; cq=cash[cash.REPORT_DATE_NAME.eq('2026一季报')].iloc[0]
q1={'revenue_yi':q.TOTALOPERATEREVE/1e8,'parent_np_yi':q.PARENTNETPROFIT/1e8,'deduct_np_yi':q.KCFJCXSYJLR/1e8,'ocf_yi':cq.NETCASH_OPERATE/1e8,'capex_yi':cq.CONSTRUCT_LONG_ASSET/1e8,'fcf_yi':(cq.NETCASH_OPERATE-cq.CONSTRUCT_LONG_ASSET)/1e8,'gross_margin_pct':q.XSMLL,'net_margin_pct':q.XSJLL,'roe_pct':q.ROEJQ,'debt_asset_pct':q.ZCFZL,'eps':q.EPSJB,'bps':q.BPS}
# PB history
pb=pd.read_csv('data/002270/valuation_baidu_市净率_20260706.csv')
current_pb=5.70
pb_stats={'min':pb.value.min(),'p25':pb.value.quantile(.25),'median':pb.value.median(),'p75':pb.value.quantile(.75),'max':pb.value.max(),'current_percentile':(pb.value<=current_pb).mean()*100}
# Peer valuation
peer=pd.read_csv('data/002270/peer_valuation_20260706.csv')
# Dividend aggregate per fiscal year (declared for reporting period, including interim and quarter)
div=pd.read_csv('data/002270/dividend_em_20260706.csv')
div['year']=div['报告期'].str[:4]
div_recent=div[div['year'].isin(['2021','2022','2023','2024','2025'])].groupby('year')['现金分红-现金分红比例'].sum().reset_index()
div_recent['cash_div_per_share_yuan']=div_recent['现金分红-现金分红比例']/10
# Current inputs
price=19.86; shares=896225431; net_cash=(1011026186.57+0)-(380034333.35+77300482.62+90933615.87+392732475.00)
ev=(price*shares - net_cash)/1e8
summary={'trend':df.to_dict(orient='records'),'q1_2026':q1,'cagr_2021_2025':{'revenue':cagr_rev*100,'parent_np':cagr_np*100},'pb_stats':pb_stats,'dividend':div_recent.to_dict(orient='records'),'ev_yi':ev,'net_cash_yi':net_cash/1e8,'market_cap_yi':price*shares/1e8,'peer':peer.to_dict(orient='records')}
os.makedirs('data/002270',exist_ok=True)
open('data/002270/analysis_summary_20260706.json','w',encoding='utf-8').write(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
