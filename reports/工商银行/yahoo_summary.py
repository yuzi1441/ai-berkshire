import urllib.request, json
for sym in ['601398.SS','1398.HK']:
 u=f'https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=price,summaryDetail,defaultKeyStatistics,financialData'
 print('\n',sym)
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  raw=urllib.request.urlopen(req,timeout=20).read().decode('utf-8')
  print(raw[:1000])
 except Exception as e: print('ERR',repr(e))
