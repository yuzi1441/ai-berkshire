import akshare as ak, pandas as pd
pd.set_option('display.max_columns',100)
for fn,args in [('stock_individual_info_em',{'symbol':'601398'}),('stock_bid_ask_em',{'symbol':'601398'}),('stock_hk_fhpx_detail_ths',{'symbol':'01398'})]:
 print('\n',fn)
 try:
  print(getattr(ak,fn)(**args).to_string())
 except Exception as e: print('ERR',type(e).__name__,e)
