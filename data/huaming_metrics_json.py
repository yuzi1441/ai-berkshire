import pandas as pd, json, pathlib, math, re
from decimal import Decimal
out=pathlib.Path('data/huaming_002270')
df=pd.read_csv(out/'eastmoney_financial_abstract.csv')
metrics=['营业总收入','归母净利润','扣非净利润','经营现金流量净额','营业成本','股东权益合计(净资产)','商誉','毛利率','销售净利率','资产负债率','基本每股收益']
periods=['20260331','20251231','20250930','20250630','20250331','20241231','20240930','20240630','20240331','20231231']
res={}
for m in metrics:
    row=df[df['指标'].eq(m)]
    if row.empty: continue
    res[m]={p: (None if pd.isna(row.iloc[0][p]) else float(row.iloc[0][p])) for p in periods if p in df.columns}
print(json.dumps(res,ensure_ascii=False,indent=2))
# parse quote
qt=(out/'quote_tencent.txt').read_text('utf-8')
fields=qt.split('"')[1].split('~')
for i,v in enumerate(fields[:60]): print(i,v)
print('80-90')
for i,v in enumerate(fields[60:95],60): print(i,v)
