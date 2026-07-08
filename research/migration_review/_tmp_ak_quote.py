import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 200)
for fn,args in [
 ('stock_zh_a_spot_em',{}),
 ('stock_zh_a_hist',{'symbol':'600900','period':'daily','start_date':'20260706','end_date':'20260707','adjust':''}),
 ('stock_individual_info_em',{'symbol':'600900'}),
]:
 print('\n###', fn)
 try:
  df=getattr(ak,fn)(**args)
  print(type(df), df.shape if hasattr(df,'shape') else '')
  print(df.head(20).to_string())
 except Exception as e:
  print('ERR',repr(e))
