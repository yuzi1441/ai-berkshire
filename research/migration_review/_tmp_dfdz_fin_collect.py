import akshare as ak, pandas as pd, json
symbol='000682'
dates=['20260331','20251231','20241231','20231231','20221231','20211231','20201231']
for date in dates:
    print('\nDATE',date)
    for name,func in [('yjbb',ak.stock_yjbb_em),('lrb',ak.stock_lrb_em),('zcfz',ak.stock_zcfz_em),('xjll',ak.stock_xjll_em)]:
        try:
            df=func(date=date)
            row=df[df['股票代码'].astype(str).str.zfill(6)==symbol]
            print(name, row.to_dict('records'))
        except Exception as e:
            print(name,'ERR',repr(e))
