import akshare as ak, pandas as pd
pd.set_option('display.max_columns',None); pd.set_option('display.max_colwidth',200)
for fn,args in [
('stock_profit_sheet_by_report_em',('SH688235',)),
('stock_balance_sheet_by_report_em',('SH688235',)),
('stock_cash_flow_sheet_by_report_em',('SH688235',)),
('stock_financial_us_report_em',('ONC','年报')),
('stock_financial_hk_report_em',('06160','年报')),
]:
    try:
        df=getattr(ak,fn)(*args)
        print('\n###',fn,df.shape)
        print(df.head(3).to_string())
        print(df.tail(3).to_string())
    except Exception as e: print('\nERR',fn,type(e).__name__,e)