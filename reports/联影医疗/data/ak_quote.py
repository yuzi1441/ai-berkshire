import akshare as ak
for fn,args in [
 ('stock_zh_a_spot_em',{}),
]:
    try:
        df=getattr(ak,fn)(**args)
        print(fn, df.shape, df.columns[:20].tolist())
        row=df[df.astype(str).apply(lambda col: col.str.contains('688271', na=False)).any(axis=1)]
        print(row.head().to_string())
    except Exception as e:
        print(fn,'ERR',repr(e))
try:
    df=ak.stock_zh_a_hist(symbol='688271', period='daily', start_date='20260706', end_date='20260706', adjust='')
    print('hist',df.shape,df.to_string())
except Exception as e:
    print('hist ERR',repr(e))
