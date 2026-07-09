import akshare as ak
import pandas as pd, pathlib, json
out=pathlib.Path('data/600420'); out.mkdir(parents=True, exist_ok=True)
print('akshare version', getattr(ak,'__version__',None))
# try financial indicator
for name, func_call in [
 ('financial_abstract', lambda: ak.stock_financial_abstract(symbol='600420')),
 ('indicator', lambda: ak.stock_financial_analysis_indicator(symbol='600420')),
 ('zh_a_hist', lambda: ak.stock_zh_a_hist(symbol='600420', period='daily', start_date='20260708', end_date='20260708', adjust='')),
]:
    try:
        df=func_call()
        print('\n',name, df.shape)
        print(df.head().to_string())
        df.to_csv(out/f'akshare_{name}_20260708.csv', index=False, encoding='utf-8-sig')
    except Exception as e:
        print('\nERR', name, type(e).__name__, e)
