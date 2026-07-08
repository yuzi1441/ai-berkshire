import akshare as ak
import pandas as pd
for fn,args in [
 ('stock_zh_a_spot_em',()),
]:
 try:
  df=getattr(ak,fn)(*args)
  row=df[df.astype(str).apply(lambda s: s.str.contains('002270|华明装备', na=False)).any(axis=1)]
  print(fn, row.to_string())
 except Exception as e:
  print(fn,'ERR',repr(e))
try:
 hist=ak.stock_zh_a_hist(symbol='002270',period='daily',start_date='20260706',end_date='20260706',adjust='')
 print('hist',hist.to_string())
except Exception as e: print('hist err',e)
