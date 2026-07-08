import akshare as ak, pandas as pd, json
pd.set_option('display.max_columns', 200); pd.set_option('display.width', 240)
code='601126'
funcs=[
 ('stock_financial_abstract', lambda: ak.stock_financial_abstract(symbol=code)),
 ('stock_financial_analysis_indicator', lambda: ak.stock_financial_analysis_indicator(symbol=code,start_year='2020')),
 ('stock_lrb_em', lambda: ak.stock_lrb_em(date='20260331')),
 ('stock_zcfz_em', lambda: ak.stock_zcfz_em(date='20260331')),
 ('stock_xjll_em', lambda: ak.stock_xjll_em(date='20260331')),
 ('stock_lrb_em_20251231', lambda: ak.stock_lrb_em(date='20251231')),
 ('stock_zcfz_em_20251231', lambda: ak.stock_zcfz_em(date='20251231')),
 ('stock_xjll_em_20251231', lambda: ak.stock_xjll_em(date='20251231')),
]
for name,fn in funcs:
 print('\n###',name)
 try:
  df=fn()
  print('shape',getattr(df,'shape',None))
  print('cols',list(df.columns)[:80] if hasattr(df,'columns') else '')
  if hasattr(df,'to_csv'):
   # filter code
   f=df[df.astype(str).apply(lambda row: row.str.contains(code).any(), axis=1)] if len(df)>30 else df
   print(f.head(30).to_string())
   f.to_csv(f'sources/sifang/{name}.csv', index=False, encoding='utf-8-sig')
 except Exception as e: print('ERR',type(e).__name__,e)
