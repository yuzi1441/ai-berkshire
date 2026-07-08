import akshare as ak, pandas as pd
pd.set_option('display.max_colwidth', 160)
for cat in ['全部','董事会','股东大会','权益分派','日常经营','公司治理','股权变动']:
    try:
        df=ak.stock_zh_a_disclosure_report_cninfo(symbol='600900', market='沪深京', category='' if cat=='全部' else cat, start_date='20240101', end_date='20260707')
        print('\n###',cat, df.shape, list(df.columns))
        print(df.head(15).to_string())
    except Exception as e:
        print(cat, 'ERR', repr(e))
