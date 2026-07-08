import akshare as ak, pandas as pd, pathlib, requests, re, json
symbols={'东方电子':'000682','国电南瑞':'600406','许继电气':'000400','四方股份':'601126'}
rows=[]
for name,sym in symbols.items():
    try:
        df=ak.stock_financial_abstract(symbol=sym)
        def get(ind, date):
            m=df[df['指标'].eq(ind)]
            return float(m.iloc[0][date]) if len(m) and pd.notna(m.iloc[0].get(date)) else None
        row={'公司':name,'代码':sym}
        for d in ['20260331','20251231','20250331','20241231']:
            row[f'{d}_收入']=get('营业总收入',d)
            row[f'{d}_归母']=get('归母净利润',d)
            row[f'{d}_扣非']=get('扣非净利润',d)
            row[f'{d}_经营现金流']=get('经营现金流量净额',d)
            row[f'{d}_eps']=get('基本每股收益',d)
            row[f'{d}_bvps']=get('每股净资产',d)
        rows.append(row)
    except Exception as e:
        print('ERR fin',name,e)
# quotes from tencent
for row in rows:
    prefix='sh' if row['代码'].startswith('6') else 'sz'
    try:
        r=requests.get(f'https://qt.gtimg.cn/q={prefix}{row["代码"]}',headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'},timeout=10)
        r.encoding='gbk'; txt=r.text
        data=txt.split('="',1)[1].rstrip('";').split('~')
        # indices known: 3 current, 4 prev close, 30 change,31 pct,32 high,33 low,38 turnover%,39 pe dynamic?, 45 mcap? 46 float mcap?, 80? total shares
        row['腾讯价']=float(data[3]); row['腾讯时间']=data[30] if len(data)>30 else ''
        row['腾讯涨跌幅']=data[32] if len(data)>32 else ''
        row['腾讯总市值亿']=float(data[45]) if len(data)>45 and data[45] else None
        row['腾讯PE_TTM']=float(data[39]) if len(data)>39 and data[39] else None
        row['腾讯PB']=float(data[46]) if len(data)>46 and data[46] else None
        # print indices to inspect 东方电子 only
        if row['代码']=='000682':
            print('tencent fields len',len(data));
            for i,v in enumerate(data[:90]): print(i,v)
    except Exception as e: print('ERR quote',row['公司'],e)
df=pd.DataFrame(rows)
out=pathlib.Path('sources')/'东方电子'/'peer_metrics.csv'
df.to_csv(out,index=False,encoding='utf-8-sig')
print(df.to_string(index=False))