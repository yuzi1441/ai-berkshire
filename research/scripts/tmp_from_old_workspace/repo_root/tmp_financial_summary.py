from pathlib import Path
import akshare as ak, pandas as pd, json
pd.set_option('display.max_columns', 200)
df=ak.stock_financial_abstract(symbol='601126')
cols=['指标','20251231','20241231','20231231','20221231','20211231','20260331']
keywords=['归母净利润','营业总收入','扣非净利润','净资产收益率','基本每股收益','每股经营性现金流','销售毛利率','资产负债率','经营活动产生的现金流量净额','净利润现金含量','总资产周转率']
sub=df[df['指标'].astype(str).apply(lambda x:any(k in x for k in keywords))]
print(sub[cols].to_string(index=False))
