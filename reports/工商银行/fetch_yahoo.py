import json, urllib.request
for sym in ['601398.SS','1398.HK']:
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d'
    print('---',sym)
    try:
        req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        data=json.load(urllib.request.urlopen(req, timeout=20))
        r=data['chart']['result'][0]
        print(json.dumps({'meta':r['meta'], 'timestamp':r.get('timestamp'), 'quote':r['indicators']['quote'][0]}, ensure_ascii=False)[:2000])
    except Exception as e:
        print('ERR',repr(e))
