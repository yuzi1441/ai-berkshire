import akshare as ak
symbol='000400'
funcs=['stock_financial_abstract','stock_financial_abstract_ths','stock_financial_abstract_new_ths','stock_financial_benefit_ths','stock_financial_cash_ths','stock_financial_debt_ths','stock_financial_report_sina']
for f in funcs:
 print('\n---',f,'---')
 try:
  fn=getattr(ak,f)
  if f=='stock_financial_report_sina':
   for st in ['利润表','资产负债表','现金流量表']:
    try:
     df=fn(stock='sz000400', symbol=st)
     print(st, df.shape, df.head(3).to_string())
    except Exception as e: print(st,'err',repr(e))
  else:
   df=fn(symbol=symbol)
   print(df.shape)
   print(df.head(8).to_string())
 except Exception as e: print('err',repr(e))
