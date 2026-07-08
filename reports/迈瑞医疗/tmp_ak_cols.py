import akshare as ak, pandas as pd
pd.set_option('display.max_rows',200)
df=ak.stock_financial_abstract(symbol='300760')
print(df[['选项','指标','20260331','20251231','20241231','20231231','20221231','20211231']].to_string())
