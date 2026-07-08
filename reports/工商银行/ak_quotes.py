import akshare as ak
import pandas as pd
pd.set_option('display.max_columns',100)
for fn,args in [
 ('stock_zh_a_spot_em',()),
 ('stock_hk_spot_em',()),
]:
 print('\nFN',fn)
 try:
  df=getattr(ak,fn)(*args)
  print(df.head())
  print(df[df.astype(str).apply(lambda row: row.str.contains('工商银行|601398|01398|1398', case=False, regex=True).any(), axis=1)].head(10).to_string())
 except Exception as e: print('ERR',type(e).__name__,e)
