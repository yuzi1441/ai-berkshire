import requests, json, datetime
url='https://query1.finance.yahoo.com/v7/finance/quote?symbols=ONC'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, r.text[:500])
try:
 data=r.json()['quoteResponse']['result'][0]
 keys=['regularMarketPrice','regularMarketTime','marketCap','sharesOutstanding','regularMarketPreviousClose','regularMarketChangePercent']
 print({k:data.get(k) for k in keys})
except Exception as e: print(e)
