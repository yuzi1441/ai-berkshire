import os
for k in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:
    os.environ.pop(k, None)
import akshare as ak
for code in ['sh600312','600312']:
    try:
        df=ak.stock_zh_a_daily(symbol=code)
        print('daily', code, df.tail(5).to_string(index=False))
    except Exception as e: print('ERR daily', code, type(e).__name__, e)
try:
    df=ak.stock_zh_a_hist(symbol='600312', period='daily', start_date='20260701', end_date='20260707', adjust='')
    print('hist', df.to_string(index=False))
except Exception as e: print('ERR hist', type(e).__name__, e)
try:
    df=ak.stock_zh_a_hist_min_em(symbol='600312', period='1', start_date='2026-07-07 09:30:00', end_date='2026-07-07 15:00:00')
    print('min', df.tail().to_string(index=False))
except Exception as e: print('ERR min', type(e).__name__, e)
