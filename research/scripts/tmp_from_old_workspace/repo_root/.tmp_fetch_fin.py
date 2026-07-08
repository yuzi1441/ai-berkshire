import akshare as ak
import pandas as pd, json, os
pd.set_option('display.max_columns', None)
for name, func, args in [
('indicator_em', ak.stock_financial_analysis_indicator_em, dict(symbol='600276.SH', indicator='按报告期')),
('profit_em', ak.stock_profit_sheet_by_report_em, dict(symbol='SH600276')),
('balance_em', ak.stock_balance_sheet_by_report_em, dict(symbol='SH600276')),
('cash_em', ak.stock_cash_flow_sheet_by_report_em, dict(symbol='SH600276')),
('abstract_sina', ak.stock_financial_abstract, dict(symbol='600276')),
('analysis_sina', ak.stock_financial_analysis_indicator, dict(symbol='600276', start_year='2021')),
]:
 print('\n###', name)
 try:
  df=func(**args)
  print(df.shape)
  print(df.head(8).to_string())
  os.makedirs('data/hengrui', exist_ok=True)
  df.to_csv(f'data/hengrui/{name}.csv', index=False, encoding='utf-8-sig')
 except Exception as e:
  print('ERR',type(e).__name__,e)
