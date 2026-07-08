import pandas as pd, math, json, re
from pathlib import Path
# Load akshare abstract and extract rows
fin=pd.read_csv('data/sy_stock_financial_abstract.csv')
cols=['20260331','20251231','20241231','20231231','20221231','20211231','20201231']
def row(ind):
    r=fin[fin['指标'].eq(ind)]
    if r.empty:
        r=fin[fin['指标'].astype(str).str.contains(ind, regex=False, na=False)]
    return r.iloc[0]
items=['营业总收入','归母净利润','扣非净利润','经营现金流量净额','净资产收益率(ROE)','毛利率','销售净利率','资产负债率','每股净资产','基本每股收益','每股企业自由现金流量','每股股东自由现金流量']
print('--- selected financials from akshare abstract ---')
for item in items:
    r=row(item)
    print(item, {c:r[c] for c in cols if c in r and pd.notna(r[c])})
# Quote parse Tencent
quote=Path('data/sy_tencent_trustTrue.txt').read_text(encoding='utf-8',errors='ignore')
inside=quote.split('="',1)[1].rsplit('"',1)[0]
parts=inside.split('~')
for i,v in enumerate(parts): print(i, v)
