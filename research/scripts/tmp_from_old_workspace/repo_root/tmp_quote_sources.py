import requests, json, time
urls=[
 'https://query1.finance.yahoo.com/v8/finance/chart/000400.SZ?range=5d&interval=1d',
 'https://query1.finance.yahoo.com/v10/finance/quoteSummary/000400.SZ?modules=price,summaryDetail,defaultKeyStatistics,financialData',
 'https://stock.xueqiu.com/v5/stock/quote.json?symbol=SZ000400&extend=detail',
 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.000400&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260701&end=20260707',
]
headers={'User-Agent':'Mozilla/5.0','Referer':'https://xueqiu.com/'}
for u in urls:
 print('---',u)
 try:
  r=requests.get(u,headers=headers,timeout=20)
  print(r.status_code, r.headers.get('content-type'))
  print(r.text[:1500])
 except Exception as e: print(type(e),e)