import akshare as ak, pandas as pd, json, urllib.request
codes=['002226','002683','002096','603227','002827','603977']
names={'002226':'江南化工','002683':'广东宏大','002096':'易普力','603227':'雪峰科技','002827':'高争民爆','603977':'国泰集团'}

def price_yahoo(code):
    suffix='.SZ' if code.startswith(('0','3')) else '.SS'
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{code}{suffix}?range=5d&interval=1d'
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    data=json.loads(urllib.request.urlopen(req, timeout=15).read())['chart']['result'][0]
    return float(data['meta']['regularMarketPrice']), data['meta'].get('regularMarketTime')

def annual(df):
    df=df.copy(); df['REPORT_DATE']=pd.to_datetime(df['REPORT_DATE']); return df[df['REPORT_DATE'].dt.strftime('%m-%d')=='12-31'].sort_values('REPORT_DATE')
for code in codes:
    prefix='SZ' if code.startswith(('0','3')) else 'SH'
    try:
        price,t=price_yahoo(code)
        profit=annual(ak.stock_profit_sheet_by_report_em(symbol=prefix+code)).tail(1).iloc[0]
        bal=annual(ak.stock_balance_sheet_by_report_em(symbol=prefix+code)).tail(1).iloc[0]
        shares=float(bal.get('SHARE_CAPITAL'))
        mcap=price*shares
        rev=float(profit.get('TOTAL_OPERATE_INCOME'))
        np=float(profit.get('PARENT_NETPROFIT'))
        equity=float(bal.get('TOTAL_PARENT_EQUITY'))
        print(json.dumps({'code':code,'name':names[code],'price':price,'shares':shares,'mcap':mcap,'rev':rev,'np':np,'equity':equity,'pe':mcap/np if np else None,'pb':mcap/equity if equity else None,'ps':mcap/rev if rev else None}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'code':code,'name':names[code],'error':repr(e)}, ensure_ascii=False))
