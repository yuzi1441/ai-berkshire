import akshare as ak, pandas as pd, json, sys
pd.set_option('display.max_columns', 200); pd.set_option('display.width', 260); pd.set_option('display.max_rows', 80)

def show(name, func, *args, **kw):
    print('\n====', name, '====')
    try:
        df=func(*args, **kw)
        print(type(df), getattr(df,'shape',None))
        print(df.head(8).to_string())
        print('columns', list(df.columns))
        return df
    except Exception as e:
        print('ERR', repr(e))

show('individual', ak.stock_individual_info_em, symbol='600900')
# spot all can be slow
spot=show('spot', ak.stock_zh_a_spot_em)
if spot is not None:
    row=spot[spot['代码'].astype(str)=='600900']
    print(row.T.to_string())
show('indicator_sina?', ak.stock_financial_analysis_indicator, symbol='600900')
show('indicator_em?', ak.stock_financial_analysis_indicator_em, symbol='600900')
show('abstract_ths', ak.stock_financial_abstract_ths, symbol='600900', indicator='按报告期')
show('abstract_new_ths', ak.stock_financial_abstract_new_ths, symbol='600900')
show('profit_em', ak.stock_profit_sheet_by_report_em, symbol='SH600900')
show('balance_em', ak.stock_balance_sheet_by_report_em, symbol='SH600900')
show('cash_em', ak.stock_cash_flow_sheet_by_report_em, symbol='SH600900')
try:
    print('\n==== dividend ===')
    df=ak.stock_history_dividend_detail(symbol='600900', indicator='分红')
    print(df.head(20).to_string()); print(df.columns)
except Exception as e: print('ERR dividend',repr(e))
