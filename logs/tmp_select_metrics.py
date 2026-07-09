import pandas as pd, pathlib, json, math
f=pathlib.Path('data/600420/akshare_financial_abstract_20260708.csv')
df=pd.read_csv(f)
metrics=['营业总收入','归母净利润','扣非净利润','经营现金流量净额','股东权益合计(净资产)','商誉','基本每股收益','每股净资产','净资产收益率(ROE)','总资产报酬率(ROA)','毛利率','销售净利率','期间费用率','资产负债率']
cols=['指标','20260331','20251231','20241231','20231231','20221231','20211231']
sel=[]
seen={}
for m in metrics:
    rows=df[df['指标']==m]
    if len(rows)>0:
        # if duplicate, first is common indicators for initial metrics, but for ratio duplicates choose first generally
        row=rows.iloc[0][cols].to_dict()
        sel.append(row)
out=pd.DataFrame(sel)
out.to_csv('data/600420/selected_financial_metrics.csv',index=False,encoding='utf-8-sig')
print(out.to_string(index=False))
