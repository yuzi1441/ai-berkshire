import akshare as ak
import pandas as pd
pd.set_option('display.max_columns', None)
for fn,args in [
 ('stock_financial_abstract', {'symbol':'300760'}),
 ('stock_financial_analysis_indicator', {'symbol':'300760'}),
]:
 print('\n###',fn)
 try:
  df=getattr(ak,fn)(**args)
  print(df.head().to_string())
  print(df.tail().to_string())
  print(df.columns.tolist())
 except Exception as e:
  print('ERR',type(e),e)
