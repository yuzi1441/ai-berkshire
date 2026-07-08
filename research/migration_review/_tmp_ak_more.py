import akshare as ak, inspect, pandas as pd
pd.set_option('display.max_columns', 40)
for f in ['stock_financial_abstract_new_ths','stock_financial_abstract_ths','stock_financial_analysis_indicator_em','stock_financial_report_sina','stock_zh_a_disclosure_report_cninfo','stock_report_disclosure','stock_notice_report']:
 print('\n##',f)
 fn=getattr(ak,f)
 try: print(inspect.signature(fn))
 except Exception as e: print('sig err',e)
 try:
  if f in ['stock_financial_abstract_new_ths','stock_financial_abstract_ths','stock_financial_analysis_indicator_em']:
   df=fn(symbol='688271')
  elif f=='stock_financial_report_sina':
   df=fn(stock='sh688271', symbol='资产负债表')
  elif f=='stock_zh_a_disclosure_report_cninfo':
   df=fn(symbol='沪深京', market='沪深京', keyword='联影医疗', category='年报')
  elif f=='stock_report_disclosure':
   df=fn(market='沪深京')
  elif f=='stock_notice_report':
   df=fn(symbol='全部', date='20260429')
  print(df.head(10).to_string())
 except Exception as e: print('ERR',type(e).__name__,e)
