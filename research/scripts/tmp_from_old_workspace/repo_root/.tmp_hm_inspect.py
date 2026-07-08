import akshare as ak
import pandas as pd
symbol='002270'
for fn,args in [
    ('stock_individual_info_em', {'symbol':symbol}),
    ('stock_zh_a_spot_em', {}),
]:
    print('\n---', fn, '---')
    try:
        df=getattr(ak,fn)(**args)
        print(type(df), df.shape)
        print(df.head().to_string())
    except Exception as e:
        print('ERR', type(e).__name__, e)

for fn,args in [
    ('stock_financial_abstract', {'symbol':symbol}),
    ('stock_financial_analysis_indicator', {'symbol':symbol}),
    ('stock_balance_sheet_by_report_em', {'symbol':'SZ'+symbol}),
    ('stock_profit_sheet_by_report_em', {'symbol':'SZ'+symbol}),
    ('stock_cash_flow_sheet_by_report_em', {'symbol':'SZ'+symbol}),
]:
    print('\n---', fn, '---')
    try:
        df=getattr(ak,fn)(**args)
        print(type(df), df.shape)
        print(df.head(10).to_string())
        print(df.columns.tolist()[:20])
    except Exception as e:
        print('ERR', type(e).__name__, e)
