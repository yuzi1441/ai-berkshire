import pandas as pd, pathlib, math
src=pathlib.Path('reports/联影医疗/sources')
df=pd.read_csv(src/'selected_metrics.csv')
cols=['20251231','20241231','20231231','20221231','20211231','20201231']
for _,r in df.drop_duplicates('指标').iterrows():
 print(r['指标'], {c:r[c] for c in cols if c in r and pd.notna(r[c])})
# compute CAGRs 2020-2025 revenue, net profit
rev=df[df['指标']=='营业总收入'].iloc[0]; np=df[df['指标']=='归母净利润'].iloc[0]
for name,row in [('Revenue',rev),('NP',np)]:
 start=row['20201231']; end=row['20251231']; cagr=(end/start)**(1/5)-1
 print(name,start,end,cagr)
# revenue 2025 by source from pages values
shares=824157988
print('Revenue per share', 13800251663.95/shares)
print('FCF per share CFO-Capex', (2679018849.49-2093181965.21)/shares)
print('Net cash rough cash+trading - debt', 5502937108.96+4926542409.75-944721233.21-58753856.21)
