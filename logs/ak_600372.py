import akshare as ak, pandas as pd, json, pathlib
pd.set_option('display.max_columns', None); pd.set_option('display.width', 200)
funcs=[('abstract', lambda: ak.stock_financial_abstract(symbol='600372')), ('indicator', lambda: ak.stock_financial_analysis_indicator(symbol='600372')), ('indicator_em', lambda: ak.stock_financial_analysis_indicator_em(symbol='600372')), ('sina', lambda: ak.stock_financial_report_sina(stock='sh600372', symbol='资产负债表'))]
for name,fn in funcs:
    print('\nFUNC',name)
    try:
        df=fn(); print(df.shape); print(df.head().to_string())
        pathlib.Path('data/600372').mkdir(parents=True, exist_ok=True)
        df.to_csv(f'data/600372/{name}.csv', index=False, encoding='utf-8-sig')
    except Exception as e:
        print('ERR',type(e).__name__,e)