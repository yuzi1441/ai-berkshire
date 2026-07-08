import akshare as ak
for func,args in [(ak.stock_fhps_detail_em, {'symbol':'002270'}),(ak.stock_dividend_cninfo, {'symbol':'002270'}),(ak.stock_fhps_detail_ths, {'symbol':'002270'})]:
 print('\n',func.__name__)
 try:
  df=func(**args); print(df.shape); print(df.head(20).to_string()); print(df.columns.tolist())
 except Exception as e: print('ERR',type(e).__name__,e)
