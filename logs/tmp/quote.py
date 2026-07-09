import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 200)
for func,args in [
 ('stock_zh_a_spot_em', {}),
 ('stock_individual_info_em', {'symbol':'002226'}),
]:
 print('\n###',func)
 try:
  df=getattr(ak,func)(**args)
  if func=='stock_zh_a_spot_em':
   df=df[df['代码'].astype(str)=='002226']
  print(df.to_string())
 except Exception as e:
  print('ERR',repr(e))
