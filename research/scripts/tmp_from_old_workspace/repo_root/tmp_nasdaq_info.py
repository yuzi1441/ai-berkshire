import requests
for url in ['https://api.nasdaq.com/api/quote/ONC/info?assetclass=stocks','https://api.nasdaq.com/api/quote/ONC/realtime-trades?limit=1&fromTime=00:00']:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Origin':'https://www.nasdaq.com','Referer':'https://www.nasdaq.com/market-activity/stocks/onc'},timeout=20)
 print('\n',url,r.status_code,r.text[:800])
