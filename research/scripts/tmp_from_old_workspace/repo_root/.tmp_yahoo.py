import requests, json, time
for sym in ['ONC','BGNE']:
 url=f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=1m'
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15)
  print(sym,r.status_code,r.text[:300])
  if r.status_code==200:
   j=r.json()['chart']['result'][0]
   print(json.dumps(j['meta'],indent=2)[:1000])
 except Exception as e: print(sym,e)