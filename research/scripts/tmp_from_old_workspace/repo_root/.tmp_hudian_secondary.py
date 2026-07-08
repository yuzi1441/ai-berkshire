import akshare as ak, pandas as pd
pd.set_option('display.max_columns', None); pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 80)
for name, call in [
 ('zygc_em', lambda: ak.stock_zygc_em(symbol='SZ002463')),
 ('profile_cninfo', lambda: ak.stock_profile_cninfo(symbol='002463')),
 ('main_holder_sina', lambda: ak.stock_main_stock_holder(stock='002463')),
 ('top10_em', lambda: ak.stock_gdfx_top_10_em(symbol='sz002463', date='20260331')),
]:
 print('\n---',name,'---')
 try:
  df=call(); print(df.head(30).to_string(index=False)); df.to_csv(f'data/hudian_{name}.csv',index=False,encoding='utf-8-sig')
 except Exception as e: print('ERR',type(e).__name__,e)
