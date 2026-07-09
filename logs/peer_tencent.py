import requests, json, pathlib, pandas as pd
symbols={'600372':'sh600372','600760':'sh600760','600893':'sh600893','600038':'sh600038','000768':'sz000768'}
rows=[]
for code,sym in symbols.items():
    r=requests.get('https://qt.gtimg.cn/q='+sym,timeout=15)
    text=r.content.decode('gbk','ignore')
    vals=text.split('=\"',1)[1].rsplit('\"',1)[0].split('~') if '=\"' in text else []
    def f(i):
        try: return float(vals[i]) if len(vals)>i and vals[i] else None
        except Exception: return None
    row={'code':code,'name':vals[1] if len(vals)>1 else '', 'price':f(3), 'time':vals[30] if len(vals)>30 else '', 'pe_ttm':f(39), 'mkt_cap_billion':f(44), 'pb':f(46), 'shares':f(72), 'raw':text}
    rows.append(row)
    print(row)
pathlib.Path('data/600372').mkdir(exist_ok=True,parents=True)
pd.DataFrame([{k:v for k,v in r.items() if k!='raw'} for r in rows]).to_csv('data/600372/peer_tencent_quotes_20260709.csv',index=False,encoding='utf-8-sig')
json.dump(rows,open('data/600372/peer_tencent_quotes_20260709.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)