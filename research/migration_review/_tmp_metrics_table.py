import akshare as ak, pandas as pd, pathlib, json
fa=ak.stock_financial_abstract(symbol='601088')
cols=['20251231','20241231','20231231','20221231','20211231']
keys=['净资产收益率(ROE)','毛利率','销售净利率','资产负债率','经营现金流量净额','归母净利润','营业总收入','基本每股收益','每股净资产']
for opt in ['常用指标','盈利能力','财务风险','每股指标']:
 print('\nOPT',opt)
 sub=fa[(fa['选项']==opt)&(fa['指标'].isin(keys))]
 print(sub[['指标']+cols].to_string(index=False))
# calculate averages
for metric in ['净资产收益率(ROE)','毛利率','销售净利率','资产负债率']:
 row=fa[(fa['选项']=='常用指标')&(fa['指标']==metric)]
 if row.empty: row=fa[fa['指标']==metric].head(1)
 vals=[float(row[c].iloc[0]) for c in cols]
 print(metric, vals, sum(vals)/len(vals))