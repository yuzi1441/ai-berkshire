import akshare as ak, pandas as pd, json, os, requests, re
from pathlib import Path
base=Path('sources/pgdq'); base.mkdir(parents=True, exist_ok=True)
symbol='600312'
for category in ['年报','一季报','半年报','三季报','业绩预告','分红配股','投资者关系']:
    try:
        df=ak.stock_zh_a_disclosure_report_cninfo(symbol=symbol, market='沪深京', category=category, start_date='20200101', end_date='20260707')
        print('\nCAT', category, df.shape)
        print(df.head(10).to_string())
        df.to_csv(base/f'cninfo_{category}.csv', index=False, encoding='utf-8-sig')
    except Exception as e:
        print('ERR', category, repr(e))
# spot and fundamentals
try:
    spot=ak.stock_zh_a_spot_em(); row=spot[spot['代码']==symbol]
    print('\nSPOT'); print(row.T.to_string()); row.to_csv(base/'spot_em.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('spot err',repr(e))
try:
    info=ak.stock_individual_info_em(symbol=symbol); print('\nINFO'); print(info.to_string()); info.to_csv(base/'individual_info_em.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('info err',repr(e))
for name in ['stock_financial_analysis_indicator','stock_profit_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_cash_flow_sheet_by_report_em','stock_dividend_cninfo','stock_fhps_detail_em']:
    try:
        fn=getattr(ak,name)
        kwargs={'symbol':symbol}
        if name=='stock_financial_analysis_indicator': kwargs['start_year']='2020'
        df=fn(**kwargs)
        print('\nFUNC', name, df.shape); print(df.head(8).to_string())
        df.to_csv(base/f'{name}.csv',index=False,encoding='utf-8-sig')
    except Exception as e: print('ERR', name, repr(e))
