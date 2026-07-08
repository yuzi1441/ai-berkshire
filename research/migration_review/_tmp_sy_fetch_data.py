import akshare as ak, pandas as pd, json, traceback
pd.set_option('display.max_columns', 100)
pd.set_option('display.width', 240)

def trycall(name, fn, *args, **kwargs):
    print('\n###', name)
    try:
        df=fn(*args, **kwargs)
        print(type(df), getattr(df,'shape',None))
        print(df.head(10).to_string())
        return df
    except Exception as e:
        print('ERR', repr(e))
        traceback.print_exc(limit=1)

trycall('stock_zh_a_spot_em', ak.stock_zh_a_spot_em)
trycall('stock_zh_a_hist 601088 daily', ak.stock_zh_a_hist, symbol='601088', period='daily', start_date='20260706', end_date='20260706', adjust='')
trycall('stock_zh_a_hist 601088 recent', ak.stock_zh_a_hist, symbol='601088', period='daily', start_date='20260701', end_date='20260706', adjust='')
trycall('stock_hk_hist 01088 recent', ak.stock_hk_hist, symbol='01088', period='daily', start_date='20260701', end_date='20260706', adjust='')
trycall('stock_financial_analysis_indicator 601088', ak.stock_financial_analysis_indicator, symbol='601088', start_year='2021')
trycall('stock_financial_report_sina balance', ak.stock_financial_report_sina, stock='sh601088', symbol='资产负债表')
trycall('stock_financial_report_sina profit', ak.stock_financial_report_sina, stock='sh601088', symbol='利润表')
trycall('stock_financial_report_sina cash', ak.stock_financial_report_sina, stock='sh601088', symbol='现金流量表')
