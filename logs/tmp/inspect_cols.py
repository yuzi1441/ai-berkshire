import akshare as ak, pandas as pd, json
for func,args in [
 ('stock_cash_flow_sheet_by_report_em', {'symbol':'SZ002226'}),
 ('stock_balance_sheet_by_report_em', {'symbol':'SZ002226'}),
 ('stock_profit_sheet_by_report_em', {'symbol':'SZ002226'}),
 ('stock_financial_analysis_indicator_em', {'symbol':'002226'}),
]:
 df=getattr(ak,func)(**args)
 print('\n###', func, 'shape', df.shape)
 print('\n'.join(df.columns.tolist()))
 print('HEAD')
 print(df.head(3).to_string())
