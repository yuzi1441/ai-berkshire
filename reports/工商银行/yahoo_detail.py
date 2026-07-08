import urllib.request, json
symbols=['601398.SS','1398.HK']
for sym in symbols:
 u=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1mo&interval=1d'
 req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
 data=json.load(urllib.request.urlopen(req,timeout=20))
 r=data['chart']['result'][0]
 print('\n',sym,r['meta'])
 for ts,close in zip(r['timestamp'][-10:], r['indicators']['quote'][0]['close'][-10:]):
  import datetime
  print(datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d'), close)
