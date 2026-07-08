import os
import akshare as ak, pandas as pd
pd.set_option('display.max_columns', None)
for fn,args in [
    ('stock_zh_a_spot_em',()),
    ('stock_zh_a_hist',('688235','daily','20260701','20260706','qfq')),
]:
    try:
        df=getattr(ak,fn)(*args)
        print('\n',fn,df.shape)
        if fn=='stock_zh_a_spot_em':
            row=df[df.astype(str).apply(lambda col: col.str.contains('百济神州|688235', regex=True, na=False)).any(axis=1)]
            print(row.to_string())
        else:
            print(df.to_string())
    except Exception as e: print('\n',fn,'ERR',type(e).__name__,e)