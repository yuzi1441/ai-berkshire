import akshare as ak
import pandas as pd
pd.set_option('display.max_columns', 80)
pd.set_option('display.width', 200)
code='601126'
print('ak version', getattr(ak,'__version__',None))
# quote realtime
for fn,args in [
 ('stock_zh_a_spot_em',()),
 ('stock_individual_info_em',(code,)),
 ('stock_bid_ask_em',(code,)),
 ('stock_zh_a_hist',(code,)),
 ('stock_financial_abstract',(code,)),
 ('stock_financial_analysis_indicator',(code,)),
]:
    try:
        f=getattr(ak,fn)
        print('\n---',fn,'---')
        if fn=='stock_zh_a_spot_em':
            df=f(); print(df[df.astype(str).apply(lambda row: row.str.contains(code).any(), axis=1)].head().to_string())
        elif fn=='stock_zh_a_hist':
            df=f(symbol=code, period='daily', start_date='20260101', end_date='20260707', adjust=''); print(df.tail().to_string())
        elif fn=='stock_financial_analysis_indicator':
            df=f(symbol=code, start_year='2020'); print(df.tail(10).to_string())
        else:
            res=f(*args); print(res.tail(20).to_string() if hasattr(res,'tail') else res)
    except Exception as e:
        print('ERR',fn,type(e).__name__,e)
# list financial related funcs containing lrb/zcfz/xjll/financial
print('\nfuncs sample')
print([x for x in dir(ak) if 'financial' in x.lower() or 'lrb' in x.lower() or 'zcfz' in x.lower() or 'xjll' in x.lower()][:100])
