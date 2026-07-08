import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 50); pd.set_option('display.width', 200)
for kwargs in [
 dict(symbol='601088', market='沪深京', keyword='年度报告', start_date='20260101', end_date='20260707'),
 dict(symbol='601088', market='沪深京', keyword='第一季度报告', start_date='20260401', end_date='20260707'),
 dict(symbol='601088', market='沪深京', keyword='利润分配', start_date='20260101', end_date='20260707'),
]:
 print('\nKWARGS',kwargs)
 try:
  df=ak.stock_zh_a_disclosure_report_cninfo(**kwargs)
  print(df.shape)
  print(df.head(10).to_string())
  print(list(df.columns))
 except Exception as e: print('ERR',repr(e))