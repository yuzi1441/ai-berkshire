import akshare as ak, pandas as pd, pathlib
out=pathlib.Path('reports/长江电力/sources'); out.mkdir(parents=True,exist_ok=True)
for name,call in [
 ('ths_abstract', lambda: ak.stock_financial_abstract_ths(symbol='600900', indicator='按报告期')),
 ('ths_new', lambda: ak.stock_financial_abstract_new_ths(symbol='600900')),
 ('profit_em', lambda: ak.stock_profit_sheet_by_report_em(symbol='SH600900')),
 ('cash_em', lambda: ak.stock_cash_flow_sheet_by_report_em(symbol='SH600900')),
 ('balance_em', lambda: ak.stock_balance_sheet_by_report_em(symbol='SH600900')),
 ('dividend', lambda: ak.stock_history_dividend_detail(symbol='600900', indicator='分红')),
]:
  try:
    df=call()
    print(name, df.shape, list(df.columns)[:20])
    df.to_csv(out/f'ak_{name}.csv',index=False,encoding='utf-8-sig')
    print(df.head(3).to_string())
  except Exception as e: print('ERR',name,repr(e))
