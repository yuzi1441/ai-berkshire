import akshare as ak
import pandas as pd
code='600312'
funcs=[
 ('individual_info', lambda: ak.stock_individual_info_em(symbol=code)),
 ('spot_em', lambda: ak.stock_zh_a_spot_em()),
 ('financial_indicator', lambda: ak.stock_financial_analysis_indicator(symbol=code)),
 ('financial_indicator_em', lambda: ak.stock_financial_analysis_indicator_em(symbol=code)),
 ('profit_report', lambda: ak.stock_profit_sheet_by_report_em(symbol=code)),
 ('balance_report', lambda: ak.stock_balance_sheet_by_report_em(symbol=code)),
 ('cash_report', lambda: ak.stock_cash_flow_sheet_by_report_em(symbol=code)),
 ('zygc', lambda: ak.stock_zygc_em(symbol=code)),
 ('fhps', lambda: ak.stock_fhps_detail_em(symbol=code)),
]
for name,fn in funcs:
 print('\n====',name,'====')
 try:
  df=fn()
  print(type(df), getattr(df,'shape',None))
  print(df.head(10).to_string())
  print('cols:', list(df.columns)[:80])
 except Exception as e:
  print('ERR',repr(e))
