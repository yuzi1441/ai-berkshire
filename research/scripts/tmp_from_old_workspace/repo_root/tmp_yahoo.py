import requests, time, json
symbols=['ONC','BGNE']
for sym in symbols:
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
    print(sym, r.status_code, r.text[:200])
