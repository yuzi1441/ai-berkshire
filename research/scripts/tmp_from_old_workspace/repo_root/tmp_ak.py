try:
 import akshare as ak
 print('akshare', ak.__version__)
 # try indicators
 for func,args in [
  ('stock_financial_abstract', {'symbol':'002270'}),
  ('stock_financial_analysis_indicator', {'symbol':'002270'}),
 ]:
  try:
   f=getattr(ak,func); df=f(**args); print(func, df.shape); print(df.head().to_string()); print(df.tail().to_string())
  except Exception as e: print(func,'ERR',repr(e))
except Exception as e: print('no akshare',repr(e))
