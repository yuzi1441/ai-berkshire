import akshare as ak
import pandas as pd
for cat in ['年报','一季报']:
 print('\nCAT',cat)
 try:
  df=ak.stock_zh_a_disclosure_report_cninfo(symbol='002270', market='沪深京', category=cat, start_date='20210101', end_date='20260706')
  print(df.shape)
  print(df.head(20).to_string())
  print(df.columns.tolist())
 except Exception as e:
  print('ERR',type(e).__name__,e)
