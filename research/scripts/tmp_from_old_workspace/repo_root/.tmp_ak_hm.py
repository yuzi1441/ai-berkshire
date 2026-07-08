import akshare as ak, json, pandas as pd
symbol='002270'
try:
    df=ak.stock_zh_a_spot_em()
    row=df[df['代码']==symbol]
    print('spot', row.to_string(index=False))
except Exception as e: print('spot_err',repr(e))
for fn,args in [
    ('stock_financial_abstract', {'symbol':symbol}),
    ('stock_financial_analysis_indicator', {'symbol':symbol}),
]:
    try:
        f=getattr(ak,fn)
        df=f(**args)
        print('\nFN',fn,df.shape)
        print(df.head(10).to_string())
        Path='sources/cninfo_hmzb/'+fn+'.csv'
        df.to_csv(Path,index=False,encoding='utf-8-sig')
    except Exception as e: print('ERR',fn,repr(e))