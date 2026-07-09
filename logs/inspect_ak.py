import akshare as ak
try:
    df=ak.stock_zh_a_spot_em()
    print(df.head().to_string())
    print(df.columns.tolist())
except Exception as e:
    print('ERR',repr(e))
