import akshare as ak, pandas as pd, json, os
pd.set_option('display.max_columns', None)
print('hist')
try:
 df=ak.stock_zh_a_hist(symbol='600276', period='daily', start_date='20260701', end_date='20260706', adjust='')
 print(df.tail(10).to_string(index=False))
 df.to_csv('data/hengrui/price_hist_20260706.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('hist err',type(e).__name__,e)
print('\nspot')
try:
 sp=ak.stock_zh_a_spot_em()
 row=sp[sp['代码'].astype(str)=='600276']
 print(row.to_string(index=False))
 row.to_csv('data/hengrui/spot_em_20260706.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('spot err',type(e).__name__,e)
