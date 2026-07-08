import urllib.request, json, time
symbols=['601398.SS','1398.HK']
for sym in symbols:
 u=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d'
 print('URL',u)
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  data=json.load(urllib.request.urlopen(req,timeout=20))
  r=data['chart']['result'][0]
  print(sym, r['meta'].get('regularMarketPrice'), r['meta'].get('currency'), r['timestamp'][-3:], r['indicators']['quote'][0]['close'][-3:])
 except Exception as e: print('ERR',e)
