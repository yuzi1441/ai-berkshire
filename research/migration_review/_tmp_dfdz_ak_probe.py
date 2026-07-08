import akshare as ak
import pandas as pd
symbol='000682'
funcs = ['stock_zh_a_spot_em','stock_financial_analysis_indicator','stock_profit_sheet_by_report_em','stock_cash_flow_sheet_by_report_em','stock_balance_sheet_by_report_em','stock_yjbb_em','stock_lrb_em','stock_zcfz_em','stock_xjll_em','stock_individual_info_em']
for f in funcs:
    print('\nFUNC', f)
    try:
        obj=getattr(ak,f)
        if f=='stock_financial_analysis_indicator': df=obj(symbol=symbol)
        elif f.endswith('_by_report_em'): df=obj(symbol=symbol)
        elif f in ['stock_yjbb_em','stock_lrb_em','stock_zcfz_em','stock_xjll_em']: df=obj(date='20260331')
        elif f=='stock_individual_info_em': df=obj(symbol=symbol)
        else: df=obj()
        print(type(df), getattr(df,'shape',None))
        print(df.head().to_string())
        print(df.columns.tolist() if hasattr(df,'columns') else '')
    except Exception as e:
        print('ERR', repr(e))
