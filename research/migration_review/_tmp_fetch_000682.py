import akshare as ak, pandas as pd
pd.set_option('display.max_columns',50); pd.set_option('display.width',200)
for cat in ['年报','一季报']:
 print('\nCNINFO',cat)
 try:
  df=ak.stock_zh_a_disclosure_report_cninfo(symbol='000682', market='沪深京', category=cat, start_date='20250101', end_date='20260707')
  print(df.head(10).to_string())
  print(df.columns.tolist())
 except Exception as e: print(type(e),e)
print('\nEastmoney notices')
try:
 df=ak.stock_individual_notice_report(security='000682', symbol='财务报告', begin_date='2025-01-01', end_date='2026-07-07')
 print(df.head(20).to_string()); print(df.columns.tolist())
except Exception as e: print(type(e),e)

for f in ['stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em']:
 print('\nEM',f)
 try:
  df=getattr(ak,f)(symbol='SZ000682')
  print(df.head(8).to_string()); print(df.columns.tolist()[:30])
 except Exception as e: print(type(e),e)
