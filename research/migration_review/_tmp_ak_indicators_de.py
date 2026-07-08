import pandas as pd, pathlib
p=pathlib.Path('sources')/'东方电子'/'akshare_东方电子_财务摘要.csv'
df=pd.read_csv(p)
for opt in df['选项'].dropna().unique():
    sub=df[df['选项']==opt]
    print('\n##',opt)
    print('\n'.join(sub['指标'].astype(str).tolist()[:80]))