import akshare as ak, pandas as pd
pd.set_option('display.max_columns', 50)
funcs=['stock_zh_a_spot_em','stock_individual_info_em','stock_financial_abstract','stock_financial_analysis_indicator','stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em']
for f in funcs:
 print('\n##',f)
 try:
  fn=getattr(ak,f)
  if f=='stock_zh_a_spot_em':
   df=fn(); print(df[df.astype(str).apply(lambda r: r.str.contains('688271|联影医疗', regex=True).any(), axis=1)].head().to_string())
  elif f=='stock_individual_info_em': print(fn(symbol='688271').to_string())
  elif f=='stock_financial_abstract': print(fn(symbol='688271').head(20).to_string())
  elif f=='stock_financial_analysis_indicator': print(fn(symbol='688271').head(20).to_string())
  else: print(fn(symbol='688271').head(5).to_string())
 except Exception as e: print('ERR',type(e).__name__,e)
