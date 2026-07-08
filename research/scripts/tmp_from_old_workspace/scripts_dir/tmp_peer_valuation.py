import pandas as pd, requests, os, json, math
codes={'002270':'SZ','002028':'SZ','002452':'SZ','600406':'SH','600089':'SH'}
rows=[]
for code,mkt in codes.items():
    sym=f'{code}.{mkt}'
    try:
        ind=pd.read_csv(f'data/002270/indicator_em_20260706.csv') if code=='002270' else None
        if code!='002270':
            import akshare as ak
            ind=ak.stock_financial_analysis_indicator_em(symbol=sym)
            os.makedirs(f'data/peers/{code}',exist_ok=True)
            ind.to_csv(f'data/peers/{code}/indicator_em_20260706.csv',index=False,encoding='utf-8-sig')
        r=ind[ind['REPORT_DATE_NAME'].eq('2025年报')].iloc[0]
        rows.append({'code':code,'name':r['SECURITY_NAME_ABBR'],'rev_2025':r['TOTALOPERATEREVE'],'np_2025':r['PARENTNETPROFIT'],'roe_2025':r['ROEJQ'],'gross_margin_2025':r['XSMLL'],'net_margin_2025':r['XSJLL'],'debt_asset_2025':r['ZCFZL'],'eps_2025':r['EPSJB'],'bps_2025':r['BPS']})
    except Exception as e:
        rows.append({'code':code,'err':str(e)})
# Tencent quote parse
url='https://qt.gtimg.cn/q='+','.join([('sh' if m=='SH' else 'sz')+c for c,m in codes.items()])
t=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20).text
quote={}
for part in t.split(';'):
    if '="' in part:
        arr=part.split('="',1)[1].rstrip('"').split('~')
        if len(arr)>73:
            quote[arr[2]]={'price':float(arr[3]), 'pe_ttm':float(arr[39]) if arr[39] else None, 'mktcap_billion':float(arr[45]) if arr[45] else None, 'pb':float(arr[46]) if arr[46] else None, 'total_shares':float(arr[73]) if arr[73] else None, 'div_yield':float(arr[49]) if arr[49] else None, 'time':arr[30], 'raw':arr}
for row in rows:
    q=quote.get(row['code'],{})
    row.update({k:v for k,v in q.items() if k!='raw'})
    if 'eps_2025' in row and q.get('price'):
        row['pe_2025_static']=q['price']/row['eps_2025'] if row['eps_2025'] else None
        row['pb_2025_static']=q['price']/row['bps_2025'] if row['bps_2025'] else None
pd.DataFrame(rows).to_csv('data/002270/peer_valuation_20260706.csv',index=False,encoding='utf-8-sig')
print(pd.DataFrame(rows).to_string(index=False))
print('quote url',url)
