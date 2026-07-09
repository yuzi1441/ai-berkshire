import akshare as ak
import pandas as pd
pd.set_option('display.max_columns', 200)
items = [
 ('stock_financial_abstract', {'symbol':'002226'}),
 ('stock_financial_analysis_indicator_em', {'symbol':'002226'}),
 ('stock_balance_sheet_by_report_em', {'symbol':'SZ002226'}),
 ('stock_cash_flow_sheet_by_report_em', {'symbol':'SZ002226'}),
 ('stock_profit_sheet_by_report_em', {'symbol':'SZ002226'}),
]
for func,args in items:
    print('\n###',func)
    try:
        df=getattr(ak,func)(**args)
        print(df.head(12).to_string())
        print('shape', df.shape)
        print('columns', df.columns.tolist())
    except Exception as e:
        print('ERR',type(e).__name__,str(e))
