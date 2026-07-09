import akshare as ak, pandas as pd, json
from pathlib import Path
codes=['002270','688676','601179','002028','600089']
rows=[]
for c in codes:
    try:
        df=ak.stock_zh_a_hist(symbol=c, period='daily', start_date='20260101', end_date='20260708', adjust='qfq')
        # columns 日期 开盘 收盘 最高 最低 成交量 成交额 振幅 涨跌幅...
        df['日期']=pd.to_datetime(df['日期'])
        last=df.iloc[-1]
        last_close=float(last['收盘'])
        def ret(n):
            if len(df)>n:
                base=float(df.iloc[-1-n]['收盘']); return (last_close/base-1)*100
            return None
        avg30=df.tail(30)['成交额'].astype(float).mean()/1e8
        avg90=df.tail(90)['成交额'].astype(float).mean()/1e8
        rows.append({'code':c,'close_qfq':last_close,'return_30d_pct':ret(30),'return_90d_pct':ret(90),'avg_turnover_30d_yi':avg30,'avg_turnover_90d_yi':avg90})
    except Exception as e:
        rows.append({'code':c,'error':repr(e)})
out=Path('data/大型变压器/five_stock_momentum_liquidity_20260708.csv')
pd.DataFrame(rows).to_csv(out,index=False,encoding='utf-8-sig')
print(out.resolve())
print(pd.DataFrame(rows).to_string(index=False))
