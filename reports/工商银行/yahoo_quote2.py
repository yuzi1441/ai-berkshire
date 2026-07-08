import urllib.request, json, time, datetime
for sym in ['601398.SS','1398.HK']:
 u=f'https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}'
 print('\nURL',u)
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  print(urllib.request.urlopen(req,timeout=20).read().decode('utf-8')[:2000])
 except Exception as e: print('ERR',repr(e))
