import akshare as ak, pandas as pd
pd.set_option('display.max_columns', None); pd.set_option('display.width', 200); pd.set_option('display.max_colwidth', 120)
for cat in ['年报','一季报','半年报','三季报','业绩预告','其他']:
    try:
        df=ak.stock_zh_a_disclosure_report_cninfo(symbol='002463', market='沪深京', category=cat, start_date='20250101', end_date='20260706')
        print('\nCAT',cat, 'rows', len(df))
        print(df.head(20).to_string())
    except Exception as e:
        print('ERR',cat,type(e).__name__,e)
