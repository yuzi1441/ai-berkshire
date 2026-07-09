import akshare as ak
import pandas as pd
pd.set_option('display.max_columns', 200)
df=ak.stock_zh_a_disclosure_report_cninfo(symbol='002226', market='沪深京', keyword='年度报告', category='年报', start_date='20210101', end_date='20260709')
print(df.to_string())
print(df.columns.tolist())
