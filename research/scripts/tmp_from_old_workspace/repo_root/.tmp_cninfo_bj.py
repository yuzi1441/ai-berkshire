import akshare as ak, pandas as pd
pd.set_option('display.max_columns',None); pd.set_option('display.max_colwidth',200)
try:
    df=ak.stock_zh_a_disclosure_report_cninfo(symbol='688235', market='沪深京', category='一季报', start_date='20260401', end_date='20260531')
    print(df.shape); print(df.head(10).to_string())
except Exception as e: print('ERR',type(e).__name__,e)
try:
    df=ak.stock_zh_a_disclosure_report_cninfo(symbol='688235', market='沪深京', category='年报', start_date='20260201', end_date='20260331')
    print(df.shape); print(df.head(10).to_string())
except Exception as e: print('ERR2',type(e).__name__,e)