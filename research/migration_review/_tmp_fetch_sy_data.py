import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 50); pd.set_option('display.width', 200)
for name, call in [
 ('analysis_indicator_em', lambda: ak.stock_financial_analysis_indicator_em(symbol='601088')),
 ('financial_abstract', lambda: ak.stock_financial_abstract(symbol='601088')),
 ('financial_report_sina_balance', lambda: ak.stock_financial_report_sina(stock='sh601088', symbol='资产负债表')),
 ('financial_report_sina_profit', lambda: ak.stock_financial_report_sina(stock='sh601088', symbol='利润表')),
 ('financial_report_sina_cash', lambda: ak.stock_financial_report_sina(stock='sh601088', symbol='现金流量表')),
]:
 print('\n###', name)
 try:
  df=call()
  print(df.shape)
  print(df.head().to_string())
  print('cols', list(df.columns))
 except Exception as e:
  print('ERR', repr(e))