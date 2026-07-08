import pandas as pd
pd.set_option('display.max_rows',200)
p='data/sy_stock_financial_abstract.csv'
df=pd.read_csv(p)
print(df[['选项','指标','20260331','20251231','20241231','20231231','20221231','20211231','20201231']].to_string())
