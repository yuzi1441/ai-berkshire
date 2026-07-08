import akshare as ak, pandas as pd, traceback
pd.set_option('display.max_columns',200); pd.set_option('display.width',240)
for name,call in [
 ('stock_financial_abstract', lambda: ak.stock_financial_abstract(symbol='601398')),
 ('stock_financial_analysis_indicator', lambda: ak.stock_financial_analysis_indicator(symbol='601398')),
 ('stock_financial_analysis_indicator_em', lambda: ak.stock_financial_analysis_indicator_em(symbol='601398')),
 ('stock_financial_report_sina_balance', lambda: ak.stock_financial_report_sina(stock='sh601398', symbol='资产负债表')),
 ('stock_financial_report_sina_profit', lambda: ak.stock_financial_report_sina(stock='sh601398', symbol='利润表')),
 ('stock_financial_report_sina_cash', lambda: ak.stock_financial_report_sina(stock='sh601398', symbol='现金流量表')),
]:
 print('\n---',name,'---')
 try:
  df=call(); print(df.shape); print(df.head(10).to_string())
 except Exception as e:
  print('ERR',type(e),e); traceback.print_exc(limit=1)