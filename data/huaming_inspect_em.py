import pandas as pd, pathlib, json
p=pathlib.Path('data/huaming_002270/eastmoney_financial_abstract.csv')
df=pd.read_csv(p)
print(df.shape)
print(df.columns.tolist()[:20])
print(df.head(30).to_string())
print('indicators:', df['指标'].head(50).tolist() if '指标' in df.columns else df.iloc[:,1].head(50).tolist())
