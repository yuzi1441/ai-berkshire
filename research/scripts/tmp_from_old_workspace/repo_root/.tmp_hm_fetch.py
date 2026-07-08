import akshare as ak
import pandas as pd
symbol='SZ002270'
for name, func, kwargs in [
 ('indicator_em', ak.stock_financial_analysis_indicator_em, {'symbol':'002270.SZ'}),
 ('profit_em', ak.stock_profit_sheet_by_report_em, {'symbol':symbol}),
 ('balance_em', ak.stock_balance_sheet_by_report_em, {'symbol':symbol}),
 ('cash_em', ak.stock_cash_flow_sheet_by_report_em, {'symbol':symbol}),
 ('sina_abstract', ak.stock_financial_abstract, {'symbol':'002270'}),
 ('sina_indicator', ak.stock_financial_analysis_indicator, {'symbol':'002270','start_year':'2021'}),
]:
 print('\n###',name)
 try:
  df=func(**kwargs)
  print(df.shape)
  print(df.head(8).to_string())
  print('cols', list(df.columns)[:60])
 except Exception as e:
  print('ERR',type(e).__name__,e)
