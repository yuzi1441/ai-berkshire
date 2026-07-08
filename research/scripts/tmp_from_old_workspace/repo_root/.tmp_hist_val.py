import akshare as ak, pandas as pd, os
os.makedirs('data/002270',exist_ok=True)
for indicator in ['市盈率','市净率','总市值']:
 print('\n',indicator)
 try:
  df=ak.stock_zh_valuation_baidu(symbol='002270', indicator=indicator, period='近十年')
  print(df.shape); print(df.head().to_string()); print(df.tail().to_string()); df.to_csv(f'data/002270/valuation_baidu_{indicator}_20260706.csv',index=False,encoding='utf-8-sig')
 except Exception as e: print('ERR',type(e).__name__,e)
try:
 df=ak.stock_zh_valuation_comparison_em(symbol='SZ002270')
 print('\ncomparison',df.shape); print(df.head(20).to_string()); df.to_csv('data/002270/valuation_comparison_em_20260706.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('ERR comp',type(e).__name__,e)
