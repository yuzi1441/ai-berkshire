import akshare as ak, pandas as pd
pd.set_option('display.max_columns',80)
funcs=[
 ('stock_zh_a_hist', {'symbol':'601398','period':'daily','start_date':'20260701','end_date':'20260707','adjust':''}),
 ('stock_hk_hist', {'symbol':'01398','period':'daily','start_date':'20260701','end_date':'20260707','adjust':''}),
 ('stock_hk_hist', {'symbol':'1398','period':'daily','start_date':'20260701','end_date':'20260707','adjust':''}),
]
for fn,kw in funcs:
 print('\nFN',fn,kw)
 try:
  df=getattr(ak,fn)(**kw)
  print(df.tail().to_string())
 except Exception as e: print('ERR',type(e).__name__,e)
