import akshare as ak
import pandas as pd
from pathlib import Path

out = Path('reports/联影医疗/_raw')
out.mkdir(parents=True, exist_ok=True)

code='688271'
print('fetch spot...')
try:
    spot = ak.stock_zh_a_spot_em()
    row = spot[spot['代码'].astype(str)==code]
    print(row.T.to_string())
    row.to_csv(out/'ak_spot_688271.csv', index=False, encoding='utf-8-sig')
except Exception as e:
    print('spot_err', repr(e))

for fn,name in [
    (ak.stock_financial_abstract_ths,'ths_abstract'),
]:
    try:
        print('fetch', name)
        df=fn(symbol=code, indicator='按年度')
        print(df.head().to_string())
        df.to_csv(out/f'{name}.csv', index=False, encoding='utf-8-sig')
    except Exception as e:
        print(name,'err',repr(e))

# Eastmoney financial analysis indicators
try:
    print('fetch em indicator')
    df=ak.stock_financial_analysis_indicator(symbol=code, start_year='2020')
    print(df.tail().to_string())
    df.to_csv(out/'em_financial_analysis_indicator.csv', index=False, encoding='utf-8-sig')
except Exception as e:
    print('em_indicator_err',repr(e))

# Financial reports by report date
for kind in ['资产负债表','利润表','现金流量表']:
    try:
        print('fetch zcfz/lrb/xjll?', kind)
    except Exception as e: print(e)
