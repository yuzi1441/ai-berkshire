import akshare as ak, pandas as pd, json, os
pd.set_option('display.max_rows', 200)
df=ak.stock_financial_abstract(symbol='002270')
print(df[['选项','指标']].to_string())
