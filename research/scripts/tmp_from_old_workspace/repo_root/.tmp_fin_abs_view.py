import pandas as pd, glob
f='data/tmp_cypc_stock_financial_abstract.csv'
df=pd.read_csv(f)
print(df.shape)
print(df.columns.tolist())
print(df.head(20).to_string())
