import requests, json, datetime
sym='ONC'
r=requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d',headers={'User-Agent':'Mozilla/5.0'},timeout=20)
data=r.json()['chart']['result'][0]
meta=data['meta']
print(json.dumps({k:meta.get(k) for k in ['currency','symbol','exchangeName','regularMarketPrice','regularMarketTime','fiftyTwoWeekHigh','fiftyTwoWeekLow','chartPreviousClose','priceHint']}, indent=2))
print(datetime.datetime.fromtimestamp(meta['regularMarketTime']))
print(data['timestamp'])
print(data['indicators']['quote'][0])
