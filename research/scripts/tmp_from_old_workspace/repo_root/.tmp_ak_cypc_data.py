import akshare as ak, pandas as pd, json
pd.set_option('display.max_columns', None); pd.set_option('display.max_colwidth', 120)
items=[]
for fn,args in [
('stock_individual_info_em', {'symbol':'600900'}),
('stock_financial_analysis_indicator', {'symbol':'600900','start_year':'2020'}),
('stock_profit_sheet_by_report_em', {'symbol':'SH600900'}),
('stock_cash_flow_sheet_by_report_em', {'symbol':'SH600900'}),
('stock_balance_sheet_by_report_em', {'symbol':'SH600900'}),
('stock_financial_abstract', {'symbol':'600900'}),
('stock_dividend_cninfo', {'symbol':'600900'}),
]:
    print('\n###',fn)
    try:
        df=getattr(ak,fn)(**args)
        print('shape',df.shape)
        print(df.head(12).to_string())
        df.to_csv(f'data/tmp_cypc_{fn}.csv',index=False,encoding='utf-8-sig')
    except Exception as e:
        print('ERR',type(e).__name__,repr(e))
