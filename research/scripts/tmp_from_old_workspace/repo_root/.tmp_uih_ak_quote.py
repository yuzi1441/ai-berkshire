import akshare as ak, pandas as pd
symbol='688271'
funcs=[
 ('stock_individual_info_em', lambda: ak.stock_individual_info_em(symbol=symbol)),
 ('stock_zh_a_spot_em', lambda: ak.stock_zh_a_spot_em()),
 ('stock_zh_a_hist', lambda: ak.stock_zh_a_hist(symbol=symbol, period='daily', start_date='20260706', end_date='20260706', adjust='')),
]
for name,fn in funcs:
    print('\n---',name,'---')
    try:
        df=fn()
        print(type(df), getattr(df,'shape',None))
        print(df.head(20).to_string())
        if name=='stock_zh_a_spot_em':
            row=df[df.astype(str).apply(lambda col: col.str.contains(symbol, na=False)).any(axis=1)]
            print('matched', row.to_string())
    except Exception as e:
        print('ERR',repr(e))
