import akshare as ak, pandas as pd
for f,args in [
 ('stock_zh_a_disclosure_report_cninfo', {'symbol':'600312','market':'沪市','category':'年报'}),
 ('stock_zh_a_disclosure_report_cninfo', {'symbol':'600312','market':'沪市','category':'一季报'}),
 ('stock_zh_a_disclosure_report_cninfo', {'symbol':'600312','market':'沪市','category':'半年报'}),
 ('stock_zh_a_disclosure_report_cninfo', {'symbol':'600312','market':'沪市','category':'三季报'}),
]:
 print('\n==',args,'==')
 try:
  df=getattr(ak,f)(**args)
  print(df.shape)
  print(df.head(10).to_string())
  print(df.columns.tolist())
 except Exception as e: print('ERR',repr(e))
