import pandas as pd, pathlib, json, math
path='data/600372/abstract.csv'
df=pd.read_csv(path)
cols=['指标','20260331','20251231','20241231','20231231','20221231','20211231']
sel=['归母净利润','营业总收入','营业成本','销售毛利率','净资产收益率','资产负债率','每股收益','每股净资产','经营现金流量净额','研发费用','货币资金','应收账款','存货','总资产','归属母公司股东权益']
for idx,row in df.iterrows():
    if any(s in str(row['指标']) for s in sel):
        print(idx, row['指标'], {c: row.get(c) for c in cols[1:]})