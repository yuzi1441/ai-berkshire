import akshare as ak, json, pandas as pd
print('akshare', ak.__version__)
for func,args in [
    ('stock_zh_a_spot_em',()),
    ('stock_hk_spot_em',()),
]:
    print('---',func)
    try:
        df=getattr(ak,func)(*args)
        print(df.head().to_string())
        if '代码' in df.columns:
            print(df[df['代码'].astype(str).str.contains('601398|01398', na=False)].to_string())
    except Exception as e:
        print('ERR',repr(e))
try:
    print('--- hist 601398')
    df=ak.stock_zh_a_hist(symbol='601398', period='daily', start_date='20260707', end_date='20260707', adjust='')
    print(df.to_string())
except Exception as e: print('ERR hist',repr(e))
try:
    print('--- zh individual')
    df=ak.stock_individual_info_em(symbol='601398')
    print(df.to_string())
except Exception as e: print('ERR info',repr(e))