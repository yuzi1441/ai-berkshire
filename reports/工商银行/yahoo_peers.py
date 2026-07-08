import urllib.request,json,datetime
symbols=['601288.SS','601939.SS','601988.SS','600036.SS','3988.HK','0939.HK','1288.HK','3968.HK']
for sym in symbols:
 try:
  u=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d'
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  r=json.load(urllib.request.urlopen(req,timeout=20))['chart']['result'][0]
  print(sym,r['meta'].get('regularMarketPrice'),r['meta'].get('currency'),r['meta'].get('fiftyTwoWeekHigh'),r['meta'].get('fiftyTwoWeekLow'))
 except Exception as e: print(sym,'ERR',e)
