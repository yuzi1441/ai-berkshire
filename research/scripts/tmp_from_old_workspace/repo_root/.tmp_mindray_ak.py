import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 200)
for name, func, kwargs in [
 ('notice_report', getattr(ak,'stock_notice_report',None), {'symbol':'全部'}),
 ('zh_a_spot_em', getattr(ak,'stock_zh_a_spot_em',None), {}),
 ('individual_info_em', getattr(ak,'stock_individual_info_em',None), {'symbol':'300760'}),
]:
 print('---', name, func)
 if not func: continue
 try:
  df=func(**kwargs)
  print(df.head().to_string())
  print(df.columns.tolist(), df.shape)
 except Exception as e:
  print('ERR', type(e).__name__, e)
