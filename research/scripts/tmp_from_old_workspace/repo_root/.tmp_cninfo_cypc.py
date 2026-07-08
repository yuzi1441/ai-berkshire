import akshare as ak, pandas as pd, json
pd.set_option('display.max_columns', None)
for kwargs in [dict(symbol='600900', market='沪深京', keyword='', category='年报', start_date='20250101', end_date='20260707'), dict(symbol='600900', market='沪深京', keyword='', category='一季报', start_date='20250101', end_date='20260707')]:
    print('\n###', kwargs)
    try:
        df=ak.stock_zh_a_disclosure_report_cninfo(**kwargs)
        print(df.head(10).to_string())
        print(df.columns.tolist())
    except Exception as e:
        print('ERR',repr(e))
