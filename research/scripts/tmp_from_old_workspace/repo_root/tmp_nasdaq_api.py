import requests, json
url='https://api.nasdaq.com/api/quote/ONC/summary?assetclass=stocks'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Origin':'https://www.nasdaq.com','Referer':'https://www.nasdaq.com/market-activity/stocks/onc'},timeout=20)
print(r.status_code, r.text[:500])
if r.status_code==200:
 data=r.json()['data']['summaryData']
 for k,v in data.items():
  print(k, v)
